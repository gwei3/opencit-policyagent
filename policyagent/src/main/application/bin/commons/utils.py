import stat
import tarfile
import os
import logging
from subprocess import Popen, PIPE
import hashlib
from StringIO import StringIO
from lxml import etree as ET
import shutil
import re

MODULE_NAME = 'policyagent'
LOG = logging.getLogger(MODULE_NAME)


def get_root_of_xml(xmlstring):
    try:
        tree = ET.iterparse(StringIO(xmlstring))
        for _, node in tree:
            if '}' in node.tag:
                node.tag = node.tag.split('}', 1)[1]  # Strip all namespaces.
        root = tree.root
        return root
    except Exception as e:
        LOG.exception("Failed to get root of XML file.")
        raise e


def get_loop_device(sparse_file_path):
    """
    This function associates sparse file with loop device.
    If already associated will return that loop device. If all devices are occupied will create new device and then associate.
    :param sparse_file_path: Sparse file path
    :type sparse_file_path: str
    :return: Loop device name
    :rtype: str
    """
    try:
        LOG.debug("Finding loop device linked to sparse file " + sparse_file_path)
        losetup_file_process = create_subprocess(['losetup', '-j', sparse_file_path])
        output = call_subprocess(losetup_file_process)
        call_losetup_file_process = output[0]
        if losetup_file_process.returncode == 0 and call_losetup_file_process != '':
            loop_device = call_losetup_file_process.split(":")[0]
            LOG.debug("Found attached loop device = " + loop_device)
            return loop_device

        make_proc = create_subprocess(['losetup', '--find'], None)
        output = call_subprocess(make_proc)
        loop_dev = None
        if make_proc.returncode == 0:
            loop_dev = output[0]
        if loop_dev is None:
            LOG.debug("Requires additional loop device for use")
            count = 0
            for f in os.listdir('/dev/'):
                if f.startswith('loop'):
                    num = f[4:]
                    if re.match("^([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])$", num) is not None:
                        count += 1
            device_name = '/dev/loop' + str(count)
            device = os.makedev(7, count)
            os.mknod(device_name, 0660 | stat.S_IFBLK, device)
            make_proc = create_subprocess(['losetup', '--find'])
            output = call_subprocess(make_proc)
            if make_proc.returncode == 0:
                loop_dev = output[0]
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
        LOG.exception("Failed to extract tar file!" + str(e.message))
        raise e


def create_subprocess(command, stdin=None):
    try:
        poutput = Popen(command, stdin=stdin, stdout=PIPE, stderr=PIPE)
        LOG.debug("Executing command : " + str(command))
        return poutput
    except Exception as e:
        LOG.exception("Failed while executing command " + str(command) + " " + str(e.message))
        raise e


def call_subprocess(poutput):
    """This function executes subprocess (in form of Popen object) and returns
    tuple (stdout, stderr).
    Caller can check exit code of the subprocess using Popen object's 'returncode' method.

    return: (stdout, stderr)
    :param poutput: Popen object containing subprocess command
    """
    try:
        output = poutput.communicate()
        LOG.debug("Exit status: " + str(poutput.returncode))
        if poutput.returncode != 0:
            LOG.warning("Process returned non-zero exit code: " + str(poutput.returncode))
            LOG.warning("Process STDOUT: " + output[0])
            LOG.warning("Process STDERR: " + output[1])
        return output[0].strip(), output[1].strip()
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


# Function to verify if the file is encrypted or not
def is_encrypted_file(filename):
    try:
        with open(filename) as f:
            content = f.readline()
        return True if "Salted__" in content else False
    except Exception as e:
        LOG.exception("Failed while checking encryption of file " + filename)
        raise e


# Function to create symbolic link
def create_force_symlink(target_filename, symbolic_filename):
    try:
        LOG.info("Creating link " + symbolic_filename)
        # os.remove(symbolic_filename)
        os.symlink(target_filename, symbolic_filename)
    except Exception as e:
        raise e


# Function to create a link for instance
def copy_n_create_dir_link(source_dir, target_dir):
    try:
        LOG.info("Creating a link for directory " + target_dir)
        copytree_with_permissions(source_dir, target_dir)
        shutil.rmtree(source_dir)
        create_force_symlink(target_dir, source_dir)
    except Exception as e:
        LOG.exception("Failed while creating directory symlink for " + source_dir + str(e.message))
        raise e
