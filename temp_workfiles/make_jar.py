import zipfile
import os

src_dir = r"C:\temp\jar_expand"
out_jar = r"C:\Users\TCL\Desktop\zhizhiji-final\runtime\shimejiee-local\shimejiee\Shimeji-ee.jar"

with zipfile.ZipFile(out_jar, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Use forward slashes for ZIP entry names
            arcname = os.path.relpath(file_path, src_dir).replace('\\', '/')
            zf.write(file_path, arcname)

print("JAR created:", out_jar)

# Verify patches
with zipfile.ZipFile(out_jar, 'r') as zf:
    entry_name = "com/group_finity/mascot/action/Fall.class"
    if entry_name in zf.namelist():
        data = zf.read(entry_name)
        print(f"Verify offset 4524: 0x{data[4524]:02X} (expect 0x10=bipush)")
        print(f"Verify offset 4525: 0x{data[4525]:02X} (expect 0xB0=-80)")
        print(f"Verify offset 4590: 0x{data[4590]:02X} (expect 0x03=iconst_0)")
    else:
        print("Fall.class NOT FOUND in JAR!")
        print("Available entries:", [e for e in zf.namelist() if 'Fall' in e])
