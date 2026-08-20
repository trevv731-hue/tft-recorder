import os, shutil

def clean_dir(path, name=""):
    if not os.path.exists(path):
        print(f"{name}: 不存在")
        return 0
    total = 0
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
                os.remove(fp)
                count += 1
            except: pass
        for d in dirs:
            try:
                dp = os.path.join(root, d)
                shutil.rmtree(dp, ignore_errors=True)
            except: pass
    print(f"{name}: 清理了 {count} 个文件, {total/1024/1024:.1f} MB")
    return total

# 用户临时文件
temp = os.environ.get('TEMP', '')
clean_dir(temp, "用户Temp")

# Windows临时文件
clean_dir("C:\\Windows\\Temp", "Windows Temp")

# 预取文件
clean_dir("C:\\Windows\\Prefetch", "Prefetch")

# 下载文件夹（只清理临时安装包，不删除用户文件）
# downloads = os.path.expanduser("~\\Downloads")
# print(f"下载文件夹: {downloads}")

print("\n清理完成")
