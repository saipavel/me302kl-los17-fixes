"""Host regression harness for the patched Sweet 4.0 startup paths.

Extracts actual functions from a patched source checkout. Kernel scheduling,
register operations and temperature acquisition are mocked. This is not a
kernel integration, IRQ-concurrency, hardware-throttling or boot test.
"""
from pathlib import Path
import argparse, os, re, subprocess

def function(source, name):
    match=re.search(r'(?:static\s+)?(?:int|void)\s+(?:__cpuinit\s+)?'+name+r'\([^;]*?\)\s*\{',source)
    if not match: raise ValueError('Missing function '+name)
    pos=match.end();depth=1
    while depth:
        if source[pos]=='{':depth+=1
        elif source[pos]=='}':depth-=1
        pos+=1
    return source[match.start():pos]+'\n'

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--zig',type=Path,required=True)
p.add_argument('--work',type=Path,required=True)
a=p.parse_args()
a.work.mkdir(parents=True,exist_ok=True)
t=(a.source/'drivers/thermal/msm8960_tsens.c').read_text()
c=(a.source/'drivers/thermal/msm_thermal.c').read_text()
for name,expected in [('limit_temp_degC',[80,85,92,102]),
                      ('limit_freq',[1512000,1350000,918000,384000])]:
    values=re.search(r'\b'+name+r'\[N_TEMP_LIMITS\]\s*=\s*\{([^}]+)\}',c)
    assert values and [int(x.strip()) for x in values[1].split(',')]==expected, 'Unexpected source limits: '+name
assert re.search(r'\btemp_hysteresis\s*=\s*5\s*;',c), 'Unexpected source hysteresis'
harness=r'''
#undef NDEBUG
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define EINVAL 22
#define EAGAIN 11
#define IS_ERR_OR_NULL(p) (!(p) || (uintptr_t)(p)>=(uintptr_t)-4095)
#define __cpuinit
#define NO_RELEASE_TEMPERATURE 0
#define NO_TRIGGER_TEMPERATURE -1
#define N_TEMP_LIMITS 4
#define MSM_CPUFREQ_NO_LIMIT (-1)
#define pr_info(...) ((void)0)
enum tsens_trip_type {TSENS_TRIP_STAGE3,TSENS_TRIP_STAGE2,TSENS_TRIP_STAGE1};
#define THERMAL_TRIP_ACTIVATION_ENABLED 1
struct thermal_zone_device {int dummy;};
struct work_struct {int dummy;};
struct delayed_work {int dummy;};
struct sensor {struct thermal_zone_device *tz_dev; struct work_struct *work;};
struct tm {int tsens_num_sensor;struct sensor sensor[11];};
static struct tm *tmdev;
static struct {int sensor_id;} msm_thermal_info={7};
static struct delayed_work first_work;
static struct work_struct trip_work;
static int throttled_bin=-1;
static unsigned temp_hysteresis=5;
static unsigned int limit_temp_degC[N_TEMP_LIMITS]={80,85,92,102};
static unsigned int limit_freq[N_TEMP_LIMITS]={1512000,1350000,918000,384000};
static int writes,activations,retries,samples,fail_write,last_trip,last_temp;
static int tsens_tz_set_trip_temp(struct thermal_zone_device *z,int trip,int temp) {
 assert(!IS_ERR_OR_NULL(z));writes++;last_trip=trip;last_temp=temp;return fail_write;
}
static int tsens_tz_activate_trip_type(struct thermal_zone_device *z,int trip,int enabled) {
 assert(!IS_ERR_OR_NULL(z));assert(trip==last_trip);assert(enabled==1);activations++;return 0;
}
static void check_temp_and_throttle_if_needed(struct work_struct *w) {(void)w;samples++;}
static unsigned msecs_to_jiffies(unsigned n){assert(n==100);return n;}
static int schedule_delayed_work(struct delayed_work *w,unsigned n) {
 assert(w==&first_work);assert(n==100);retries++;return 1;
}
'''
for name in ['tsens_set_tz_trip_temp_degC','tsens_set_tz_warm_temp_degC','tsens_set_tz_cool_temp_degC']:
    harness+=function(t,name)
for name in ['max_freq','limit_temp','release_temp','configure_sensor_trip_points','select_throttled_bin','check_temp']:
    harness+=function(c,name)
harness+=r'''
static void reset(void) {writes=activations=retries=samples=fail_write=0;throttled_bin=-1;}
int main(void) {
 struct tm chip={.tsens_num_sensor=11};struct thermal_zone_device zone={0};
 unsigned traces=0;
 for(int ready_at=0;ready_at<=100;ready_at++) {
  reset();tmdev=&chip;chip.sensor[7].tz_dev=NULL;chip.sensor[7].work=NULL;
  for(int n=0;n<=ready_at;n++) {
   if(n==ready_at)chip.sensor[7].tz_dev=&zone;
   check_temp(&trip_work);
   if(n<ready_at)assert(writes==0 && activations==0);
  }
  assert(retries==ready_at && writes==1 && activations==1);
  assert(samples==ready_at+1 && last_temp==80 && last_trip==TSENS_TRIP_STAGE2);
  assert(chip.sensor[7].work==&trip_work);traces++;
 }
 reset();tmdev=NULL;
 assert(tsens_set_tz_warm_temp_degC(7,80,&trip_work)==-EINVAL);traces++;
 tmdev=&chip;
 for(int id=-2;id<=12;id++)if(id<0||id>=11) {
  assert(tsens_set_tz_warm_temp_degC(id,80,&trip_work)==-EINVAL);traces++;
 }
 chip.sensor[7].tz_dev=(void*)(intptr_t)-12;
 assert(tsens_set_tz_warm_temp_degC(7,80,&trip_work)==-EAGAIN);
 check_temp(&trip_work);assert(retries==1 && writes==0);traces++;
 chip.sensor[7].tz_dev=&zone;
 for(int bin=-1;bin<4;bin++) {
  reset();throttled_bin=bin;check_temp(&trip_work);
  assert(retries==0 && samples==1);
  assert(writes==((bin==-1 || bin==3)?1:2) && activations==writes);
  if(bin==-1)assert(last_temp==80 && last_trip==TSENS_TRIP_STAGE2);
  else assert(last_temp==(int)limit_temp_degC[bin]-5 && last_trip==TSENS_TRIP_STAGE1);
  assert(max_freq(bin)==(bin==-1?-1:(int)limit_freq[bin]));traces++;
 }
 reset();fail_write=-EINVAL;
 assert(configure_sensor_trip_points()==-EINVAL);
 assert(writes==1 && activations==0);
 check_temp(&trip_work);assert(retries==0);traces++;
 /* Original hysteresis/threshold selection remains unchanged. */
 for(int bin=-1;bin<4;bin++)for(unsigned temp=0;temp<=120;temp++) {
  throttled_bin=bin;int expected=-1;
  for(int j=0;j<4;j++)if(temp>=limit_temp_degC[j])expected=j;
  if(expected<=bin && temp>(unsigned)release_temp(bin))expected=bin;
  assert(select_throttled_bin(temp)==expected);traces++;
 }
 printf("PASS: %u scenarios; missing-zone retries, recovery, invalid inputs, thresholds and hysteresis\n",traces);
 return 0;
}
'''
source=a.work/'startup-harness.c';source.write_bytes(harness.encode())
exe=a.work/('startup-harness.exe' if os.name=='nt' else 'startup-harness')
subprocess.run([str(a.zig.resolve()),'cc','-O2','-Wall','-Wextra','-Werror','-Wno-sign-compare',str(source.resolve()),'-o',str(exe.resolve())],check=True)
subprocess.run([str(exe.resolve())],check=True)
