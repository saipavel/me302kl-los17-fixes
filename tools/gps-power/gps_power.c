/* ME302KL / ARM32 legacy GPS HAL adapter. Original vendor HAL remains separate.
 * DMS power follows Android's GPS init/cleanup; navigation stays in the vendor HAL.
 * No RIL startup, NV writes, assistance deletion, or position logging.
 */
typedef unsigned size_t;
extern void *dlopen(const char *, int), *dlsym(void *, const char *);
extern void *memcpy(void *, const void *, size_t), *calloc(size_t,size_t);
extern void free(void *);
extern int __system_property_get(const char *, char *);
extern int __android_log_print(int,const char *,const char *,...);
extern int pthread_once(int *,void (*)(void));
extern int pthread_mutex_lock(int *),pthread_mutex_unlock(int *);
extern int usleep(unsigned);
#define LOG(...) __android_log_print(4,"ME302KL-GpsPower",__VA_ARGS__)
#define ORIGINAL "/vendor/lib/hw/gps.msm8960.base.so"

struct Interface {
    unsigned size;
    int (*init)(void *);
    int (*start)(void);
    int (*stop)(void);
    void (*cleanup)(void);
    void *rest[5];
};
static const struct Interface *original;
static union { struct Interface i; unsigned char storage[256]; } wrapped;
static int once, power_lock;

/* Parse complete raw QMI replies, including the mandatory successful result TLV.
 * Reject malformed, duplicate, missing, or failed result/mode fields. */
static int parse(const unsigned char *p,unsigned n,int need_mode) {
    int result=-1,mode=-1;
    unsigned off=0;
    while(off<n) {
        if(n-off<3)return -1;
        unsigned t=p[off],l=p[off+1]|((unsigned)p[off+2]<<8);off+=3;
        if(l>n-off)return -1;
        if(t==2) {
            if(l!=4 || result!=-1)return -1;
            result=p[off]|p[off+1]|p[off+2]|p[off+3];
        } else if(t==1 && need_mode) {
            if(l!=1 || mode!=-1)return -1;
            mode=p[off];
        }
        off+=l;
    }
    return result==0 ? (need_mode?mode:0) : -1;
}

typedef int (*send_fn)(void *,unsigned,void *,unsigned,void *,unsigned,unsigned *,unsigned);
static int get_mode(send_fn send,void *client) {
    unsigned char reply[64];unsigned received=0,dummy=0;
    int rc=send(client,0x2d,&dummy,0,reply,sizeof(reply),&received,2000);
    return rc || received>sizeof(reply) ? -1 : parse(reply,received,1);
}
static int set_mode(send_fn send,void *client,unsigned mode) {
    unsigned char request[]={1,1,0,(unsigned char)mode},reply[64];unsigned received=0;
    int rc=send(client,0x2e,request,sizeof(request),reply,sizeof(reply),&received,2000);
    return rc || received>sizeof(reply) ? -1 : parse(reply,received,0);
}
static int await_mode(send_fn send,void *client,unsigned target) {
    int mode=-1;
    for(unsigned attempt=0;attempt<10;attempt++) {
        mode=get_mode(send,client);
        if(mode<0 || mode==(int)target)return mode;
        usleep(100000);
    }
    return mode;
}
static int active(void) {
    char p[92];
    return __system_property_get("persist.me302kl.gps_power_control",p)==1 && p[0]=='1'
        && __system_property_get("persist.me302kl.cellular_disabled",p)==1 && p[0]=='1';
}
static int power(unsigned target) {
    if(!active())return 0;
    pthread_mutex_lock(&power_lock);
    /* Libraries intentionally remain loaded: QMI owns threads and callback code. */
    void *svc=dlopen("/vendor/lib/libqmiservices.so",2);
    void *cci=dlopen("/vendor/lib/libqmi_cci.so",2);
    int rc=-1,previous=-1,after=-1;void *client=0;
    if(!svc || !cci)goto done;
    void *(*object)(int,int,int)=dlsym(svc,"dms_get_service_object_internal_v01");
    int (*any)(void *,void *)=dlsym(cci,"qmi_client_get_any_service");
    int (*init)(void *,void *,void *,void *,void *,void **)=dlsym(cci,"qmi_client_init");
    send_fn send=dlsym(cci,"qmi_client_send_raw_msg_sync");
    int (*release)(void *)=dlsym(cci,"qmi_client_release");
    if(!object || !any || !init || !send || !release)goto done;
    void *obj=object(1,13,5);unsigned info[64]={0},os[128]={0};
    if(!obj || any(obj,info) || init(info,obj,0,0,os,&client))goto done;
    previous=get_mode(send,client);
    if(previous==(int)target)rc=0;
    else if(previous==0 || previous==1 || previous==5) {
        /* The modem may boot in SHUTTING_DOWN (5) without RIL. Use the
         * previously verified LOW_POWER transition before bringing it ONLINE. */
        if(previous==5 && target==0) {
            if(set_mode(send,client,1))goto release_client;
            if(await_mode(send,client,1)!=1)goto release_client;
        }
        if(!set_mode(send,client,target)) {
            after=await_mode(send,client,target);
            rc=after==(int)target?0:-1;
        }
    }
release_client:
    release(client);
done:
    LOG("power target=%u previous=%d verified=%d result=%d",target,previous,
        previous==(int)target?previous:after,rc);
    pthread_mutex_unlock(&power_lock);
    return rc;
}
static int wrapped_init(void *callbacks) {
    if(power(0))return -1;
    int rc=original->init(callbacks);
    LOG("vendor init result=%d",rc);
    if(rc)power(1);
    return rc;
}
static int wrapped_start(void) {
    if(power(0))return -1;
    return original->start();
}
static void wrapped_cleanup(void) {
    original->cleanup();
    power(1);
}
static void load(void) {
    void *h=dlopen(ORIGINAL,2);
    const struct Interface *(*get)(void)=h?dlsym(h,"get_gps_interface"):0;
    if(!get)return;
    const struct Interface *i=get();
    if(!i || i->size<sizeof(*i) || i->size>sizeof(wrapped) || !i->init || !i->start || !i->cleanup)return;
    original=i;memcpy(&wrapped,i,i->size);
    wrapped.i.init=wrapped_init;wrapped.i.start=wrapped_start;wrapped.i.cleanup=wrapped_cleanup;
    LOG("loaded original HAL, interface bytes=%u",i->size);
}
const struct Interface *get_gps_interface(void) {
    pthread_once(&once,load);
    return original?&wrapped.i:0;
}

/* ARM32 libhardware ABI: hw_module_t is 128 bytes, hw_device_t 64 bytes. */
struct Module;
struct Device { unsigned tag,version;struct Module *module;unsigned reserved[12];int (*close)(struct Device *); };
struct GpsDevice { struct Device common;const struct Interface *(*get)(struct GpsDevice *); };
struct Methods { int (*open)(const struct Module *,const char *,struct Device **); };
struct Module { unsigned tag;unsigned short module_api,hal_api;const char *id,*name,*author;struct Methods *methods;void *dso;unsigned reserved[25]; };
_Static_assert(sizeof(struct Module)==128,"ARM32 module ABI");
_Static_assert(sizeof(struct GpsDevice)==68,"ARM32 device ABI");
static const struct Interface *device_get(struct GpsDevice *dev) { (void)dev;return get_gps_interface(); }
static int device_close(struct Device *dev) { free(dev);return 0; }
static int device_open(const struct Module *module,const char *name,struct Device **out) {
    (void)name;
    if(!out || !get_gps_interface())return -1;
    struct GpsDevice *dev=calloc(1,sizeof(*dev));if(!dev)return -1;
    dev->common.tag=0x48574454;dev->common.module=(struct Module *)module;dev->common.close=device_close;
    dev->get=device_get;*out=&dev->common;return 0;
}
static struct Methods methods={device_open};
struct Module HMI={.tag=0x48574d54,.module_api=1,.id="gps",
    .name="ME302KL location-controlled GPS power",.author="ME302KL fixes",
    .methods=&methods};
