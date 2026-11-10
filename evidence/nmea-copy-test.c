extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern const char *dlerror(void);
extern int printf(const char *, ...);
extern int fflush(void *);

int JNI_OnLoad(void *vm, void *reserved) {
    (void)vm; (void)reserved;
    void *lib=dlopen("/system/lib/libhidlbase.so",2);
    if(!lib)return -1;
    void (*ctor)(void*)=dlsym(lib,"_ZN7android8hardware11hidl_stringC1Ev");
    void (*copy)(void*,const char*,unsigned)=dlsym(lib,"_ZN7android8hardware11hidl_string8copyFromEPKcj");
    void (*dtor)(void*)=dlsym(lib,"_ZN7android8hardware11hidl_stringD1Ev");
    unsigned (*size)(void*)=dlsym(lib,"_ZNK7android8hardware11hidl_string4sizeEv");
    const char *(*str)(void*)=dlsym(lib,"_ZNK7android8hardware11hidl_string5c_strEv");
    if(!ctor||!copy||!dtor||!size||!str)return -1;
    unsigned lengths[]={0,1,3,82,200,201};
    for(unsigned k=0;k<6;k++){
        unsigned obj[8] __attribute__((aligned(8)))={0};
        char input[202];for(unsigned i=0;i<202;i++)input[i]=(char)('A'+i%26);
        ctor(obj);copy(obj,input,lengths[k]);
        const char *s=str(obj);
        if(size(obj)!=lengths[k] || s[lengths[k]]!=0)return -1;
        for(unsigned i=0;i<lengths[k];i++)if(s[i]!=input[i])return -1;
        dtor(obj);
    }
    void *gnss=dlopen("/data/local/tmp/me302kl-gps-fix/android.hardware.gnss@1.0-impl.so",2);
    if(!gnss){printf("Patched bridge load failed: %s\n",dlerror());fflush(0);return -1;}
    printf("PASS: six unterminated-buffer cases; patched GNSS bridge links successfully\n");fflush(0);
    return 0x00010006;
}
