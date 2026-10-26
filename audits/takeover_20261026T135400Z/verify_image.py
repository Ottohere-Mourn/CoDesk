from pathlib import Path
import datetime,hashlib,json,os,subprocess,zipfile
root=Path('/data3/whn/Project2/images')
archive=root/'osworld-v2-ubuntu-x86.qcow2.zip'
expected='14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3'
assert archive.stat().st_size==14891811084

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()

actual=sha(archive)
assert actual==expected, (actual,expected)
print('ARCHIVE_SHA256_VERIFIED',flush=True)
with zipfile.ZipFile(archive) as z:
 entries=z.infolist()
 assert len(entries)==1 and entries[0].filename=='osworld-v2-ubuntu-x86.qcow2',[(e.filename,e.file_size) for e in entries]
 assert entries[0].file_size<100*1024**3
 image=root/entries[0].filename
 assert not image.exists(), 'refusing to overwrite existing image'
 z.extract(entries[0],root)
image.chmod(0o444)
env={**os.environ,'LD_LIBRARY_PATH':'/data3/whn/Project2/.codesk-tools/root/usr/lib/x86_64-linux-gnu'}
binary='/data3/whn/Project2/.codesk-tools/root/usr/bin/qemu-img'
info=json.loads(subprocess.check_output([binary,'info','--output=json',str(image)],env=env,text=True))
check=subprocess.run([binary,'check','--output=json',str(image)],env=env,capture_output=True,text=True)
result={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':actual,'expected_sha256':expected,'image':str(image),'image_sha256':sha(image),'info':info,'qemu_check_returncode':check.returncode,'qemu_check':check.stdout,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
assert check.returncode==0,check.stderr
print(json.dumps(result,indent=2),flush=True)
