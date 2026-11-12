/* Isolated pipe listener. Does not open modem, Wi-Fi or networking hardware. */
typedef unsigned long thread_t;
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern char *dlerror(void);
extern int printf(const char *,...),pipe(int *),close(int),usleep(unsigned),pthread_kill(thread_t,int),pthread_join(thread_t,void **);
extern long read(int,void *,unsigned long),write(int,const void *,unsigned long);
struct action {void (*handler)(int); unsigned long mask; int flags; void (*restorer)(void);};
extern int sigaction(int,const struct action *,struct action *);
struct map {int fd;int (*callback)(int);};
struct info {thread_t thread;struct map *map;unsigned count,capacity;int maxfd;unsigned long fdset[32];volatile unsigned char running;};
_Static_assert(__builtin_offsetof(struct info,running)==148,"ARM32 listener layout");
static volatile unsigned signalled,received;
static void caught(int sig){(void)sig;signalled++;}
static int ready(int fd){char ch; if(read(fd,&ch,1)==1)received++; return 0;}
int JNI_OnLoad(void *vm,void *reserved){(void)vm;(void)reserved;return 0x10006;}
int Java_NetmgrTest_run(void *env,void *cls,int patched){
 (void)env;(void)cls;
 write(2,"loading\n",8);
 void *lib=dlopen(patched?"/data/local/tmp/me302kl-netmgr-test/fixed.so":"/data/local/tmp/me302kl-netmgr-test/original.so",2);
 if(!lib){printf("dlopen: %s\n",dlerror());return 1;}
 int (*init)(struct info *,struct map *,unsigned)=dlsym(lib,"netmgr_nl_socklthrd_init");
 int (*add)(struct info *,int,int (*)(int))=dlsym(lib,"netmgr_nl_socklthrd_addfd");
 int (*start)(struct info *)=dlsym(lib,"netmgr_nl_socklthrd_start");
 if(!init||!add||!start)return 2;
 write(2,"symbols\n",8);
 struct info info={0};struct map map[1]={{0}};int fds[2];
 struct action action={caught,0,0,0};
 if(sigaction(44,&action,0)||pipe(fds)||init(&info,map,1)||add(&info,fds[0],ready))return 3;
 write(2,"starting\n",9);
 if(start(&info))return 3;
 for(unsigned i=0;i<100&&!info.running;i++)usleep(10000);
 if(!info.running)return 4;
 write(2,"running\n",8);
 usleep(200000);
 for(unsigned i=0;i<20;i++){
   if(pthread_kill(info.thread,44))return 5;
   usleep(20000);
 }
 if(signalled!=20)return 6;
 if(write(fds[1],"a",1)!=1)return 7;
 for(unsigned i=0;i<100&&received<1;i++)usleep(10000);
 if(received!=1)return 8;
 info.running=0;
 if(write(fds[1],"b",1)!=1||pthread_join(info.thread,0))return 9;
 close(fds[0]);close(fds[1]);
 printf("signals=%u callbacks=%u clean_join=1\n",signalled,received);
 return received==2?0:10;
}
