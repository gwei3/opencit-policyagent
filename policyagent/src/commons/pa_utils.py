import tarfile
import os,time
import logging
from subprocess import Popen, PIPE
import hashlib
import shutil

global LOG
LOG = logging.getLogger(__name__)

def untar(src, dest):
    try:
        if tarfile.is_tarfile(src):
            if not os.path.exists(dest):
                os.mkdir(dest)
            tar = tarfile.open(src, 'r')
            tar.extractall(dest)
            LOG.debug("Tar while extracted.")
            return True
        else:
            return False
    except Exception as e:
        raise Exception("Failed while doing untar"+str(e.message))

def create_subprocess(command, stdin=None):
    try:
        poutput = Popen(command, stdin=stdin, stdout=PIPE)
        return poutput
    except Exception as e:
        LOG.exception("Failed while executing subprocess command "+str(e.message))
        raise e

def call_subprocess(poutput):
    try:
        output = poutput.communicate()
        if poutput.returncode == 0:
            LOG.debug("Subprocess command executed successfully.")
            return output[0].strip()
        else:
            LOG.exception("Subprocess command failed.")
            raise Exception("Subprocess command failed.")
    except Exception as e:
        LOG.exception("Failed while executing subprocess command"+str(e.message))
        raise e

def generate_md5(filepath):
    try:
        BLOCK_SIZE=2**20
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                buf = f.read(BLOCK_SIZE)
                if not buf:
                    break
                md5.update(buf)
        return md5.hexdigest()
    except Exception as e:
        LOG.exception("Failed while doing verification of trust policy signature "+str(e.message))
        raise e

def verify_trust_policy_signature(tagent_location, policy_location):
    try:
        poutput = create_subprocess([tagent_location, "verify-trustpolicy-signature", policy_location])
        call_subprocess(poutput)
        if poutput.returncode == 0:
            LOG.debug("Trust policy signature verified.")
            return True
        else:
            LOG.debug("Trust policy signature verification failed.")
            return False
    except Exception as e:
        LOG.exception("Failed while doing verification of trust policy signature "+str(e.message))
        raise e

def copytree_with_permissions(src, dest):
    shutil.copytree(src, dest)
    st = os.stat(src)
    os.chown(dest, st.st_uid, st.st_gid)
    for f in os.listdir(src):
        src_f = os.path.join(src, f)
        st = os.stat(src_f)
        dest_f = os.path.join(dest, f)
        os.chown(dest_f, st.st_uid, st.st_gid)
