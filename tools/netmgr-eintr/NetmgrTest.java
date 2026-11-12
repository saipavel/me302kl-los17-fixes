public class NetmgrTest {
    private static native int run(int patched);
    public static void main(String[] args) {
        System.load("/data/local/tmp/me302kl-netmgr-test/libtest.so");
        int result=run(Integer.parseInt(args[0]));
        System.out.println("NETMGR TEST result="+result);
        System.exit(result==0?0:1);
    }
}
