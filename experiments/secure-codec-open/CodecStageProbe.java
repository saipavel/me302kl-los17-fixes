import java.lang.reflect.*;
public class CodecStageProbe {
 static Object call(Object o,String n,Class<?>[] t,Object...a)throws Exception{return o.getClass().getMethod(n,t).invoke(o,a);}
 public static void main(String[] args)throws Exception{
  Class.forName("android.os.Looper").getMethod("prepare").invoke(null);
  Class.forName("android.app.ActivityThread").getMethod("systemMain").invoke(null);
  Class<?> mc=Class.forName("android.media.MediaCodec"),mf=Class.forName("android.media.MediaFormat"),st=Class.forName("android.graphics.SurfaceTexture"),sf=Class.forName("android.view.Surface"),crypto=Class.forName("android.media.MediaCrypto");
  Object codec=null,texture=null,surface=null;boolean started=false;long begin=System.currentTimeMillis();
  try{
   texture=st.getConstructor(boolean.class).newInstance(false);call(texture,"setDefaultBufferSize",new Class<?>[]{int.class,int.class},320,240);
   surface=sf.getConstructor(st).newInstance(texture);
   codec=mc.getMethod("createByCodecName",String.class).invoke(null,args[0]);System.out.println("CREATE_OK ms="+(System.currentTimeMillis()-begin));
   Object format=mf.getMethod("createVideoFormat",String.class,int.class,int.class).invoke(null,"video/avc",320,240);
   mc.getMethod("configure",mf,sf,crypto,int.class).invoke(codec,format,surface,null,0);System.out.println("CONFIGURE_OK");
   call(codec,"start",new Class<?>[]{});started=true;System.out.println("START_OK");
   call(codec,"stop",new Class<?>[]{});started=false;System.out.println("STOP_OK");
  }catch(InvocationTargetException e){System.out.println("STAGE_FAILED "+e.getCause());}
  finally{
   if(codec!=null){if(started)try{call(codec,"stop",new Class<?>[]{});}catch(Exception e){}call(codec,"release",new Class<?>[]{});System.out.println("RELEASE_OK ms="+(System.currentTimeMillis()-begin));}
   if(surface!=null)call(surface,"release",new Class<?>[]{});
   if(texture!=null)call(texture,"release",new Class<?>[]{});
  }
 }
}
