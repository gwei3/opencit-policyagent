import tarfile
import os,time
import logging
from subprocess import Popen, PIPE
import hashlib
from StringIO import StringIO
from lxml import etree as ET
import shutil

MODULE_NAME = 'policyagent'
global LOG
LOG = logging.getLogger(MODULE_NAME)

def get_root_of_xml(xmlstring):
    try:
        tree = ET.iterparse(StringIO(xmlstring))
        for _, node in tree:
            if '}' in node.tag:
                node.tag = node.tag.split('}', 1)[1] # Strip all namespaces.
        root = tree.root
        return root
    except Exception as e:
        LOG.exception("Failed to get root of XML file.")
        raise e

def get_loop_device(sparse_file_path):
    try:
        make_proc = create_subprocess(['losetup', '--find'], None)
        loop_dev = call_subprocess(make_proc)
        if loop_dev is None:
            LOG.debug("Requires additional loop device for use")
            count = 0
            for f in os.listdir('/dev/'):
                if f.startswith('loop'):
                    num = f[4:]
                    if re.match("^([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])$", num) is not None:
                        count = count+1
            device_name = '/dev/loop' + str(count)
            device = os.makedev(7,count)
            os.mknod(device_name, 0660 | stat.S_ISBLK, device)
            make_proc = create_subprocess(['losetup','--find'])
            loop_dev = call_subprocess(make_proc)
        if loop_dev is not None:
            make_proc = create_subprocess(['losetup', loop_dev, sparse_file_path])
            call_subprocess(make_proc)
            if make_proc.returncode != 0:
                LOG.error("Failed while mounting loop device " + loop_dev)
                raise Exception("Failed while mounting loop device " + loop_dev)
            return loop_dev
        else:
            LOG.error("No loop device available")
            raise Exception("No loop device available")
    except Exception as e:
        LOG.exception("Failed while creating or mounting loop device!")
        raise e

def untar(src, dest):
    try:
        if tarfile.is_tarfile(src):
            if not os.path.exists(dest):
                os.mkdir(dest)
            tar = tarfile.open(src, 'r')
            tar.extractall(dest)
            LOG.debug("Tar file extracted ")
            return True
        else:
            LOG.debug("Given file " + src + " not a tarfile!")
            return False
    except Exception as e:
        raise Exception("Failed to extract tar file!")

def create_subprocess(command, stdin = None):
    try:
        poutput = Popen(command, stdin = stdin, stdout = PIPE, stderr = PIPE)
        LOG.debug("Executing command : " + str(command))
        return poutput
    except Exception as e:
        LOG.exception("Failed while executing command " + str(command) + " " + str(e.message))
        raise e

def call_subprocess(poutput):
    try:
        output = poutput.communicate()
        if poutput.returncode == 0:
            return output[0].strip()
        else:
            LOG.error(output)
            raise Exception("Command failed!")
    except Exception as e:
        LOG.exception("Command failed!")
        raise e

def generate_md5(filepath):
    try:
        BLOCK_SIZE = 2**20
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                buf = f.read(BLOCK_SIZE)
                if not buf:
                    break
                md5.update(buf)
        return md5.hexdigest()
    except Exception as e:
        LOG.exception("Failed while generating md5sum of " + filepath + " " + str(e.message))
        raise e

def copytree_with_permissions(src, dest):
    try:
        shutil.copytree(src, dest)
        st = os.stat(src)
        os.chown(dest, st.st_uid, st.st_gid)
        for f in os.listdir(src):
            src_f = os.path.join(src, f)
            st = os.stat(src_f)
            dest_f = os.path.join(dest, f)
            os.chown(dest_f, st.st_uid, st.st_gid)
    except Exception as e:
        LOG.exception("Failed while copying " + src + " to location " + dest + ": " + str(e.message))
