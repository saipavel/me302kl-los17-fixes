import java.lang.reflect.*;
import java.util.*;
import java.nio.*;
import java.nio.file.*;
public class DrmDecodeProbe {
 static Object c(Object o,String n,Class<?>[] t,Object...a)throws Exception{return o.getClass().getMethod(n,t).invoke(o,a);}
 static Class<?> K(String n)throws Exception{return Class.forName(n);}
 static void log(String s){System.out.println(s);}
 public static void main(String[] args)throws Exception{
  K("android.os.Looper").getMethod("prepare").invoke(null);K("android.app.ActivityThread").getMethod("systemMain").invoke(null);
  Object drm=null,crypto=null,ex=null,codec=null,surface=null,layer=null;byte[] session=null;
  try{
   UUID uuid=UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed");drm=K("android.media.MediaDrm").getConstructor(UUID.class).newInstance(uuid);session=(byte[])c(drm,"openSession",new Class[]{ });
   ex=K("android.media.MediaExtractor").getConstructor().newInstance();c(ex,"setDataSource",new Class[]{String.class},"/data/local/tmp/me302kl-widevine-sample.mp4");
   Object fmt=c(ex,"getTrackFormat",new Class[]{int.class},0);c(ex,"selectTrack",new Class[]{int.class},0);c(ex,"seekTo",new Class[]{long.class,int.class},20000000L,2);log("START_SAMPLE_US="+c(ex,"getSampleTime",new Class[]{}));
   Map<?,?> pssh=(Map<?,?>)c(ex,"getPsshInfo",new Class[]{});byte[] init=(byte[])pssh.get(uuid);if(init==null)throw new Exception("NO_WIDEVINE_PSSH");
   Object req=c(drm,"getKeyRequest",new Class[]{byte[].class,byte[].class,String.class,int.class,HashMap.class},session,init,"video/mp4",1,new HashMap<String,String>());
   Path response=Paths.get("/data/local/tmp/me302kl-license-response.bin");Files.deleteIfExists(response);Files.write(Paths.get("/data/local/tmp/me302kl-license-request.bin"),(byte[])c(req,"getData",new Class[]{}));log("LICENSE_REQUEST_READY");
   long deadline=System.currentTimeMillis()+180000;while(!Files.exists(response)&&System.currentTimeMillis()<deadline)Thread.sleep(250);
   c(drm,"provideKeyResponse",new Class[]{byte[].class,byte[].class},session,Files.readAllBytes(response));log("LICENSE_ACCEPTED");
   crypto=K("android.media.MediaCrypto").getConstructor(UUID.class,byte[].class).newInstance(uuid,session);log("REQUIRES_SECURE="+c(crypto,"requiresSecureDecoderComponent",new Class[]{String.class},"video/avc"));
   Object builder=K("android.view.SurfaceControl$Builder").getConstructor().newInstance();c(builder,"setName",new Class[]{String.class},"ME302KL DRM decode diagnostic");c(builder,"setBufferSize",new Class[]{int.class,int.class},320,142);layer=c(builder,"build",new Class[]{});surface=K("android.view.Surface").getConstructor().newInstance();c(surface,"copyFrom",new Class[]{K("android.view.SurfaceControl")},layer);
   codec=K("android.media.MediaCodec").getMethod("createByCodecName",String.class).invoke(null,"OMX.qcom.video.decoder.avc");c(codec,"configure",new Class[]{K("android.media.MediaFormat"),K("android.view.Surface"),K("android.media.MediaCrypto"),int.class},fmt,surface,crypto,0);c(codec,"start",new Class[]{});
   Object ci=K("android.media.MediaCodec$CryptoInfo").getConstructor().newInstance(),bi=K("android.media.MediaCodec$BufferInfo").getConstructor().newInstance();int queued=0,frames=0,encrypted=0;boolean eos=false;deadline=System.currentTimeMillis()+30000;
   while(frames<72&&System.currentTimeMillis()<deadline){
    if(!eos){int ix=(Integer)c(codec,"dequeueInputBuffer",new Class[]{long.class},1000L);if(ix>=0){ByteBuffer buf=(ByteBuffer)c(codec,"getInputBuffer",new Class[]{int.class},ix);int size=(Integer)c(ex,"readSampleData",new Class[]{ByteBuffer.class,int.class},buf,0);if(size<0||queued>=96){c(codec,"queueInputBuffer",new Class[]{int.class,int.class,int.class,long.class,int.class},ix,0,0,0L,4);eos=true;}else{long ts=(Long)c(ex,"getSampleTime",new Class[]{});boolean enc=(Boolean)c(ex,"getSampleCryptoInfo",new Class[]{K("android.media.MediaCodec$CryptoInfo")},ci);if(enc){c(codec,"queueSecureInputBuffer",new Class[]{int.class,int.class,K("android.media.MediaCodec$CryptoInfo"),long.class,int.class},ix,0,ci,ts,0);encrypted++;}else c(codec,"queueInputBuffer",new Class[]{int.class,int.class,int.class,long.class,int.class},ix,0,size,ts,0);queued++;c(ex,"advance",new Class[]{});}}}
    int out=(Integer)c(codec,"dequeueOutputBuffer",new Class[]{K("android.media.MediaCodec$BufferInfo"),long.class},bi,1000L);if(out>=0){int flags=bi.getClass().getField("flags").getInt(bi);if((flags&4)==0)frames++;c(codec,"releaseOutputBuffer",new Class[]{int.class,boolean.class},out,false);if((flags&4)!=0)break;}
   }
   log("DECODE_RESULT encrypted_inputs="+encrypted+" queued="+queued+" output_frames="+frames);c(codec,"stop",new Class[]{});
  }catch(InvocationTargetException e){log("TEST_FAILED "+e.getCause());}catch(Exception e){log("TEST_FAILED "+e);}
  finally{
   for(Object o:new Object[]{codec,ex,crypto})if(o!=null)try{c(o,"release",new Class[]{});}catch(Exception e){}
   if(surface!=null)c(surface,"release",new Class[]{});if(layer!=null){Object tr=K("android.view.SurfaceControl$Transaction").getConstructor().newInstance();c(tr,"remove",new Class[]{K("android.view.SurfaceControl")},layer);c(tr,"apply",new Class[]{});c(tr,"close",new Class[]{});c(layer,"release",new Class[]{});}
   if(drm!=null){if(session!=null)try{c(drm,"closeSession",new Class[]{byte[].class},session);}catch(Exception e){}c(drm,"release",new Class[]{});}log("CLEANUP_DONE");
  }
 }
}

