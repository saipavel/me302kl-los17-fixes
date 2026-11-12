import java.lang.reflect.*;
import java.util.UUID;
public class DrmCapabilityProbe {
 public static void main(String[] a)throws Exception{
  Class.forName("android.os.Looper").getMethod("prepare").invoke(null); Class.forName("android.app.ActivityThread").getMethod("systemMain").invoke(null);
  Class<?> c=Class.forName("android.media.MediaDrm");Object d=null;
  try{
   UUID id=UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed");
   System.out.println("WIDEVINE_SUPPORTED="+c.getMethod("isCryptoSchemeSupported",UUID.class).invoke(null,id));
   d=c.getConstructor(UUID.class).newInstance(id);
   for(String key:new String[]{"vendor","version","securityLevel"})try{System.out.println(key+"="+c.getMethod("getPropertyString",String.class).invoke(d,key));}catch(InvocationTargetException e){System.out.println(key+" unavailable: "+e.getCause().getClass().getSimpleName());}
   byte[] session=(byte[])c.getMethod("openSession").invoke(d);System.out.println("SESSION_OPEN_OK");
   Object crypto=Class.forName("android.media.MediaCrypto").getConstructor(UUID.class,byte[].class).newInstance(id,session);
   System.out.println("AVC_REQUIRES_SECURE="+crypto.getClass().getMethod("requiresSecureDecoderComponent",String.class).invoke(crypto,"video/avc"));
   crypto.getClass().getMethod("release").invoke(crypto);c.getMethod("closeSession",byte[].class).invoke(d,session);
  }catch(InvocationTargetException e){System.out.println("DRM_FAILURE="+e.getCause());}
  finally{if(d!=null)c.getMethod("release").invoke(d);}
 }
}
