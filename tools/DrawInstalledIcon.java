import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import java.io.FileOutputStream;

/** Shell-only evidence helper: render the installed icon using the phone's icon mask. */
public class DrawInstalledIcon {
    public static void main(String[] args) throws Exception {
        android.os.Looper.prepareMainLooper();
        Class<?> thread = Class.forName("android.app.ActivityThread");
        Object instance = thread.getMethod("systemMain").invoke(null);
        Context context = (Context) thread.getMethod("getSystemContext").invoke(instance);
        ApplicationInfo info = context.getPackageManager().getApplicationInfo(args[0], 0);
        Drawable icon = info.loadIcon(context.getPackageManager());
        Bitmap bitmap = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888);
        icon.setBounds(0, 0, 512, 512);
        icon.draw(new Canvas(bitmap));
        try (FileOutputStream out = new FileOutputStream(args[1])) {
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
        }
        System.out.println("Rendered installed icon: " + icon.getClass().getName());
        System.exit(0);
    }
}
