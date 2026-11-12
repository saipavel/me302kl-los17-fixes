import java.lang.reflect.*;
import java.util.*;
import java.nio.*;
import java.nio.file.*;
public class DrmAudioProbe {
 static Object c(Object o,String n,Class<?>[] t,Object...a)throws Exception{return o.getClass().getMethod(n,t).invoke(o,a);}
 static Class<?> K(String n)throws Exception{return Class.forName(n);}
 static void log(String s){System.out.println(s);}
 public static void main(String[] args)throws Exception{
  K("android.os.Looper").getMethod("prepare").invoke(null);K("android.app.ActivityThread").getMethod("systemMain").invoke(null);
  Object audio=null;long pcmBytes=0;Object drm=null,crypto=null,ex=null,codec=null,surface=null,layer=null;byte[] session=null;
  try{
   UUID uuid=UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed");drm=K("android.media.MediaDrm").getConstructor(UUID.class).newInstance(uuid);session=(byte[])c(drm,"openSession",new Class[]{ });
   ex=K("android.media.MediaExtractor").getConstructor().newInstance();c(ex,"setDataSource",new Class[]{String.class},"/data/local/tmp/me302kl-widevine-audio.mp4");
   Object fmt=c(ex,"getTrackFormat",new Class[]{int.class},0);c(ex,"selectTrack",new Class[]{int.class},0);c(ex,"seekTo",new Class[]{long.class,int.class},20000000L,2);log("START_SAMPLE_US="+c(ex,"getSampleTime",new Class[]{}));
   Map<?,?> pssh=(Map<?,?>)c(ex,"getPsshInfo",new Class[]{});byte[] init=(byte[])pssh.get(uuid);if(init==null)throw new Exception("NO_WIDEVINE_PSSH");
   Object req=c(drm,"getKeyRequest",new Class[]{byte[].class,byte[].class,String.class,int.class,HashMap.class},session,init,"audio/mp4",1,new HashMap<String,String>());
   Path response=Paths.get("/data/local/tmp/me302kl-license-response.bin");Files.deleteIfExists(response);Files.write(Paths.get("/data/local/tmp/me302kl-license-request.bin"),(byte[])c(req,"getData",new Class[]{}));log("LICENSE_REQUEST_READY");
   long deadline=System.currentTimeMillis()+180000;while(!Files.exists(response)&&System.currentTimeMillis()<deadline)Thread.sleep(250);
   c(drm,"provideKeyResponse",new Class[]{byte[].class,byte[].class},session,Files.readAllBytes(response));log("LICENSE_ACCEPTED");
   crypto=K("android.media.MediaCrypto").getConstructor(UUID.class,byte[].class).newInstance(uuid,session);log("REQUIRES_SECURE="+c(crypto,"requiresSecureDecoderComponent",new Class[]{String.class},"audio/mp4a-latm"));
   codec=K("android.media.MediaCodec").getMethod("createDecoderByType",String.class).invoke(null,"audio/mp4a-latm");c(codec,"configure",new Class[]{K("android.media.MediaFormat"),K("android.view.Surface"),K("android.media.MediaCrypto"),int.class},fmt,null,crypto,0);c(codec,"start",new Class[]{});
   Class<?> at=K("android.media.AudioTrack");int min=(Integer)at.getMethod("getMinBufferSize",int.class,int.class,int.class).invoke(null,44100,12,2);audio=at.getConstructor(int.class,int.class,int.class,int.class,int.class,int.class).newInstance(3,44100,12,2,Math.max(min,16384),1);c(audio,"play",new Class[]{});log("AUDIO_TEST_STARTED");
   Object ci=K("android.media.MediaCodec$CryptoInfo").getConstructor().newInstance(),bi=K("android.media.MediaCodec$BufferInfo").getConstructor().newInstance();int queued=0,frames=0,encrypted=0;boolean eos=false;deadline=System.currentTimeMillis()+30000;
   while(frames<480&&System.currentTimeMillis()<deadline){
    if(!eos){int ix=(Integer)c(codec,"dequeueInputBuffer",new Class[]{long.class},1000L);if(ix>=0){ByteBuffer buf=(ByteBuffer)c(codec,"getInputBuffer",new Class[]{int.class},ix);int size=(Integer)c(ex,"readSampleData",new Class[]{ByteBuffer.class,int.class},buf,0);if(size<0||queued>=500){c(codec,"queueInputBuffer",new Class[]{int.class,int.class,int.class,long.class,int.class},ix,0,0,0L,4);eos=true;}else{long ts=(Long)c(ex,"getSampleTime",new Class[]{});boolean enc=(Boolean)c(ex,"getSampleCryptoInfo",new Class[]{K("android.media.MediaCodec$CryptoInfo")},ci);if(enc){c(codec,"queueSecureInputBuffer",new Class[]{int.class,int.class,K("android.media.MediaCodec$CryptoInfo"),long.class,int.class},ix,0,ci,ts,0);encrypted++;}else c(codec,"queueInputBuffer",new Class[]{int.class,int.class,int.class,long.class,int.class},ix,0,size,ts,0);queued++;c(ex,"advance",new Class[]{});}}}
    int out=(Integer)c(codec,"dequeueOutputBuffer",new Class[]{K("android.media.MediaCodec$BufferInfo"),long.class},bi,1000L);if(out>=0){int flags=bi.getClass().getField("flags").getInt(bi);if((flags&4)==0)frames++;int size=bi.getClass().getField("size").getInt(bi),off=bi.getClass().getField("offset").getInt(bi);if(size>0){ByteBuffer pcm=(ByteBuffer)c(codec,"getOutputBuffer",new Class[]{int.class},out);pcm.position(off);pcm.limit(off+size);byte[] bytes=new byte[size];pcm.get(bytes);int pos=0;while(pos<size){int written=(Integer)c(audio,"write",new Class[]{byte[].class,int.class,int.class},bytes,pos,size-pos);if(written<=0)throw new Exception("AUDIO_WRITE_FAILED="+written);pos+=written;pcmBytes+=written;}}c(codec,"releaseOutputBuffer",new Class[]{int.class,boolean.class},out,false);if((flags&4)!=0)break;}
   }
   Thread.sleep(300);log("AUDIO_RESULT pcm_bytes="+pcmBytes+" played_frames="+c(audio,"getPlaybackHeadPosition",new Class[]{}));log("DECODE_RESULT encrypted_inputs="+encrypted+" queued="+queued+" output_frames="+frames);c(codec,"stop",new Class[]{});
  }catch(InvocationTargetException e){log("TEST_FAILED "+e.getCause());}catch(Exception e){log("TEST_FAILED "+e);}
  finally{
   if(audio!=null){try{c(audio,"stop",new Class[]{});}catch(Exception e){}c(audio,"release",new Class[]{});}for(Object o:new Object[]{codec,ex,crypto})if(o!=null)try{c(o,"release",new Class[]{});}catch(Exception e){}
   if(surface!=null)c(surface,"release",new Class[]{});if(layer!=null){Object tr=K("android.view.SurfaceControl$Transaction").getConstructor().newInstance();c(tr,"remove",new Class[]{K("android.view.SurfaceControl")},layer);c(tr,"apply",new Class[]{});c(tr,"close",new Class[]{});c(layer,"release",new Class[]{});}
   if(drm!=null){if(session!=null)try{c(drm,"closeSession",new Class[]{byte[].class},session);}catch(Exception e){}c(drm,"release",new Class[]{});}log("CLEANUP_DONE");
  }
 }
}

