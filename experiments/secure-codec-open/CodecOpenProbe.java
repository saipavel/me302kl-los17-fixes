import java.lang.reflect.*;
public class CodecOpenProbe {
 public static void main(String[] args) throws Exception {
  Class<?> l=Class.forName("android.os.Looper");l.getMethod("prepare").invoke(null);
  Class<?> at=Class.forName("android.app.ActivityThread");Object thread=at.getMethod("systemMain").invoke(null);
  Class<?> c=Class.forName("android.media.MediaCodec");Object codec=null;
  try { codec=c.getMethod("createByCodecName",String.class).invoke(null,args[0]);System.out.println("CREATE_OK "+args[0]); }
  catch(InvocationTargetException e){System.out.println("CREATE_FAILED "+e.getCause());}
  finally {if(codec!=null){c.getMethod("release").invoke(codec);System.out.println("RELEASE_OK");}}
 }
}
