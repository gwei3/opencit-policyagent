import os
import shutil
import requests
import logging
import time
from commons.parse import ParseProperty
import commons.utils as utils

#import sys
#reload(sys)
#sys.setdefaultencoding("utf-8")

LOG = None
MODULE_NAME = 'policyagent'


class Crypt(object):
    AIK_PEM = "/aik.pem"
    KEY_EXTN = ".key"
    XML_EXTN = ".xml"
    BASE_DIR = "_base"
    LOST_FOUND = "lost+found"
    DEVICE_MAPPER = "/dev/mapper/"
    #file_content = ""

    def __init__(self, config):
        """
        :type config: PolicyAgent configuration object
        """
        pa_parse = ParseProperty()
        global LOG
        LOG = logging.getLogger(MODULE_NAME)
        self.pa_config = config
        TA_PROP_FILE = "trustagent" + ((str)((int)(time.time()))) + ".properties"
        decrypt_tagent_prop_process = utils.create_subprocess([config['TAGENT_LOCATION'], 'export-config', os.path.join("/tmp", TA_PROP_FILE)])
        utils.call_subprocess(decrypt_tagent_prop_process)
        if decrypt_tagent_prop_process.returncode != 0:
            LOG.error("Failed to decrypt trustagent properties file. Exit code = " + str(decrypt_tagent_prop_process.returncode))
            raise Exception("Failed to decrypt trustagent properties file.")
        global ta_config
        ta_config = pa_parse.create_property_dict(os.path.join("/tmp", TA_PROP_FILE))
        #clean the temporary file after readng it
        os.remove(os.path.join("/tmp", TA_PROP_FILE))

    # Function to request key to KMS
    def __kms_request_key(self, aik_dir, dek_url, key_path):
        LOG.debug("kms proxy ip address :" + self.pa_config['KMSPROXY_SERVER'])
        LOG.debug("kms proxy jetty port :" + self.pa_config['KMSPROXY_SERVER_PORT'])
        LOG.debug("key URL :" + dek_url)
        try:
            if len(self.pa_config['KMSPROXY_SERVER_PORT']) and len(self.pa_config['KMSPROXY_SERVER']):
                if not os.path.isdir(self.pa_config['ENC_KEY_LOCATION']):
                    LOG.debug("Creating directory :" + self.pa_config['ENC_KEY_LOCATION'])
                    os.mkdir(self.pa_config['ENC_KEY_LOCATION'])
                proxies = {'http': 'http://' + self.pa_config['KMSPROXY_SERVER'] + ':' + self.pa_config[
                    'KMSPROXY_SERVER_PORT']}
                headers = {'Content-Type': 'application/x-pem-file', 'Accept': 'application/octet-stream'}
                with open(aik_dir + Crypt.AIK_PEM, 'rb') as f:
                    r = requests.post(dek_url, headers=headers, data=f, proxies=proxies)
                if r.status_code == requests.codes.ok:
                    fd = open(key_path, 'w')
                    fd.write(r.content)
                    fd.close()
                else:
                    LOG.error("Response code: {0}".format(r.status_code))
                    LOG.error("Response: {0}".format(r.content))
                    LOG.error("Failed to get the key " + key_path + " from the Key server.")
                    raise Exception("Failed to get the " + key_path + " from the Key server.")
            else:
                LOG.error("KMS configuration is not set in properties file.")
                raise Exception("KMS configuration is not set in properties file.")
        except Exception as e:
            LOG.exception("Failed while requesting key " + key_path + " from KMS :" + str(e.message))
            raise e

    # Function to create sparse file
    def __create_sparse_file(self, root_disk_size_gb, sparse_file_path):
        global sparse_file_size_kb
        try:
            if len(self.pa_config['SPARSE_FILE_SIZE']) == 0:
                stat = os.statvfs('/')
                sparse_file_size_kb = (stat.f_bavail * stat.f_frsize) / 1024
            else:
                stat = os.statvfs('/')
                available_space_kb = (stat.f_bavail * stat.f_frsize) / 1024
                if self.pa_config['SPARSE_FILE_SIZE'] > available_space_kb:
                    LOG.warning("The size of the sparse file in the properties file exceeds the available disk size")
                    LOG.warning("Allocating the available disk size to continue with the launch")
                    sparse_file_size_kb = available_space_kb
            root_disk_size_kb = root_disk_size_gb * 1024 * 1024
            LOG.info("Root disk size :" + str(root_disk_size_kb))
            LOG.info("Sparse file size :{0}".format(str(sparse_file_size_kb)))
            if root_disk_size_kb > sparse_file_size_kb:
                LOG.error("The size of the root disk exceeds the allocated sparse file size ")
                raise Exception("The size of the root disk exceeds the allocated sparse file size ")
            size_in_bytes = sparse_file_size_kb * 1024
            create_process_truncate = utils.create_subprocess(
                ['truncate', '-s', str(size_in_bytes), str(sparse_file_path)])
            utils.call_subprocess(create_process_truncate)
            if create_process_truncate.returncode != 0:
                LOG.error("Failed to create sparse file " + sparse_file_path + "..Exit code = " + str(
                    create_process_truncate.returncode))
                raise Exception("Failed to create sparse file")
            LOG.debug("Sparse file " + sparse_file_path + " created successfully.")
        except Exception as e:
            LOG.exception("Failed while creating sparse file: " + str(e.message))
            raise e

    # Function to create loop device, format and bind it, mount device mapper
    def create_encrypted_device(self, image_id, image_realpath, sparse_file_path, key_path, format_device=False):
        """ This function attaches loop device to sparse file, create encrypted device, open it and then mount it.
        :param image_id: Image ID of the base image
        :param image_realpath: Path of the image where should be copied in decrypted form
        :param sparse_file_path: File path of the sparse file
        :param key_path: File path of the Key file
        :param format_device: Whether to format encrypted device or not. Use this carefully. If set to true will format all content of the device (sparse file)
        :rtype: object
        """
        device_mapper = os.path.join(Crypt.DEVICE_MAPPER, image_id)
        try:
            loop_dev = utils.get_loop_device(sparse_file_path)
            if format_device:
                # Format device using cryptsetup for encryption
                with open(self.pa_config['TRUST_AGENT_LIB']) as f:
                    for line in f:
                        eq_index = line.find('=')
                        val = line[eq_index+1:].strip()
                os.environ['LD_LIBRARY_PATH'] = val # visible in this process + all children
                luks_format_proc_1 = utils.create_subprocess(
                    [self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],
                     '-i', key_path, '-q', ta_config['binding.key.secret'], '-x'])
                luks_format_proc_2 = utils.create_subprocess(
                    ['cryptsetup', '-v', '--batch-mode', 'luksFormat', '--key-file=-', loop_dev],
                    stdin=luks_format_proc_1.stdout)
                utils.call_subprocess(luks_format_proc_2)
                if luks_format_proc_2.returncode != 0:
                    LOG.error("Failed while formatting loop device " + loop_dev + " ..exit code = " + str(
                        luks_format_proc_2.returncode))
                    raise Exception("Failed while formatting loop device " + loop_dev)
                LOG.debug("Loop device formatted successfully.")
            # Check whether device is already active/open
            cryptsetup_status_proc = utils.create_subprocess(['cryptsetup', 'status', device_mapper])
            utils.call_subprocess(cryptsetup_status_proc)
            if cryptsetup_status_proc.returncode == 0:
                LOG.debug("LUKS device is already open: " + device_mapper)
            else:
                # Open LUKS device
                LOG.debug("Opening device: " + device_mapper)
                luks_open_proc_1 = utils.create_subprocess(
                    [self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],
                     '-i', key_path, '-q', ta_config['binding.key.secret'], '-x'])
                luks_open_proc_2 = utils.create_subprocess(
                    ['cryptsetup', '-v', 'luksOpen', '--key-file=-', loop_dev, image_id],
                    stdin=luks_open_proc_1.stdout)
                utils.call_subprocess(luks_open_proc_2)
                if luks_open_proc_2.returncode != 0:
                    LOG.error(
                        "Failed while key unbinding....Key =  " + key_path + " Loop device = " + loop_dev + "Exit code=" + str(
                            luks_open_proc_2.returncode))
                    raise Exception("Failed while key unbinding ..Key =  " + key_path + " Loop device = " + loop_dev)
            if format_device:
                # Format device with ext4 filesystem
                LOG.debug("Formating device: " + device_mapper)
                make_fs_status = utils.create_subprocess(['mkfs.ext4', '-v', device_mapper])
                utils.call_subprocess(make_fs_status)
                if make_fs_status.returncode != 0:
                    LOG.error("Failed while creating ext4 filesystem " + device_mapper + " ..Exit code = " + str(
                        make_fs_status.returncode))
                    raise Exception("Failed while creating ext4 filesystem " + device_mapper)
            if not os.path.ismount(image_realpath):
                LOG.debug("Mounting device: " + device_mapper)
                make_mount_process_status = utils.create_subprocess(
                    ['mount', '-t', 'ext4', device_mapper, image_realpath])
                utils.call_subprocess(make_mount_process_status)
                if make_mount_process_status.returncode != 0:
                    LOG.error("Failed while mounting device mapper " + device_mapper + " ..Exit code = " + str(
                        make_mount_process_status.returncode))
                    raise Exception("Failed while mounting device mapper " + device_mapper)
                LOG.debug("Device mapper " + device_mapper + " mounted successfully")
        except Exception as e:
            LOG.exception("Failed while creating encrypted device: " + str(e.message))
            raise e

    # Function to request key for decryption
    def request_dek(self, dek_url, key_path):
        try:
            if os.path.exists(self.pa_config['XEN_TPM']) and os.access(self.pa_config['XEN_TPM'], os.X_OK):
                if os.path.exists(self.pa_config['AIK_BLOB_FILE']):
                    create_xen_tpm_proc = utils.create_subprocess(
                        [self.pa_config['XEN_TPM'], '--get_aik_pem', self.pa_config['AIK_BLOB_FILE'],
                         '>', '/tmp' + Crypt.AIK_PEM])
                    utils.call_subprocess(create_xen_tpm_proc)
                    if create_xen_tpm_proc.returncode != 0:
                        LOG.error("Failed while requesting key..Exit code = " + str(create_xen_tpm_proc.returncode))
                        raise Exception("Failed while requesting key ")
                else:
                    create_xen_tpm_proc = utils.create_subprocess(
                        [self.pa_config['XEN_TPM'], '--get_aik_pem', '>', '/tmp' + Crypt.AIK_PEM])
                    utils.call_subprocess(create_xen_tpm_proc)
                    if create_xen_tpm_proc.returncode != 0:
                        LOG.error("Failed while requesting key..Exit code = " + str(create_xen_tpm_proc.returncode))
                        raise Exception("Failed while requesting key")
                aik_dir = "/tmp"
            else:
                aik_dir = self.pa_config['TRUST_AGENT_CONFIG_PATH']
            if not os.path.isfile(aik_dir + Crypt.AIK_PEM):
                LOG.error("Error: Missing AIK Public Key " + aik_dir + Crypt.AIK_PEM)
                raise Exception("Missing AIK Public Key " + aik_dir + Crypt.AIK_PEM)
            self.__kms_request_key(aik_dir, dek_url, key_path)
        except Exception as e:
            LOG.exception("Failed while requesting key :" + str(e.message))
            raise e

    # Function to cleanup
    def __cleanup(self, instance_link, instance_realpath, image_id):
        try:
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'], image_id + Crypt.KEY_EXTN)
            image_link = os.path.join(self.pa_config['INSTANCES_DIR'], Crypt.BASE_DIR, image_id)
            sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], image_id)
            device_mapper = os.path.join(Crypt.DEVICE_MAPPER, image_id)
            LOG.info("Starting clean_up :")
            LOG.info("Instance symbolic link = " + instance_link)
            LOG.info("Instance realpath = " + instance_realpath)
            LOG.info("Image symbolic link = " + image_link)
            LOG.info("Image realpath = " + image_realpath)
            LOG.info("Key = " + key)
            LOG.info("Sparse file path = " + sparse_file_path)
            LOG.info("Device mapper = " + device_mapper)
            if os.path.islink(instance_link):
                LOG.debug("Removing symbolic link " + instance_link)
                os.unlink(instance_link)
            if os.path.exists(instance_realpath):
                LOG.debug("Removing instance realpath " + instance_realpath)
                shutil.rmtree(instance_realpath)
            if os.path.exists(instance_link):
                LOG.debug("Removing instance directory " + instance_link)
                shutil.rmtree(instance_link)
            if os.path.exists(image_realpath):
                list_dirs = os.listdir(image_realpath)
                # remove _base and lost+found dir from list
                if Crypt.BASE_DIR in list_dirs:
                    list_dirs.remove(Crypt.BASE_DIR)
                if Crypt.LOST_FOUND in list_dirs:
                    list_dirs.remove(Crypt.LOST_FOUND)
                if len(list_dirs) == 0:
                    if os.path.exists(key):
                        LOG.debug("Removing key " + key)
                        os.remove(key)
                    if os.path.islink(image_link):
                        LOG.debug("Removing image link " + image_link + "and " + image_link + Crypt.XML_EXTN)
                        os.unlink(image_link)
                        os.remove(image_link + '.trustpolicy' + Crypt.XML_EXTN)
                    if os.path.ismount(image_realpath):
                        LOG.debug("Unmounting " + image_realpath)
                        make_umount_process_status = utils.create_subprocess(['umount', image_realpath])
                        utils.call_subprocess(make_umount_process_status)
                        if make_umount_process_status.returncode != 0:
                            LOG.debug("Failed to unmount " + image_realpath)
                    if os.path.exists(image_realpath):
                        LOG.debug("Removing image realpath " + image_realpath)
                        shutil.rmtree(image_realpath)
                    # remove sparse file
                    if os.path.exists(sparse_file_path):
                        LOG.debug("Finding loop device linked to sparse file " + sparse_file_path)
                        losetup_file_process = utils.create_subprocess(['losetup', '-j', sparse_file_path])
                        output = utils.call_subprocess(losetup_file_process)
                        call_losetup_file_process = output[0]
                        if losetup_file_process.returncode != 0 or call_losetup_file_process == '':
                            LOG.debug("Failed to find linked loop device with the sparse file " + sparse_file_path)
                        else:
                            loop_device = call_losetup_file_process.split(":")[0]
                            LOG.debug("Found loop device = " + loop_device)
                            LOG.debug("Detaching loop device " + loop_device)
                            losetup_remove_process = utils.create_subprocess(['losetup', '-d', loop_device])
                            utils.call_subprocess(losetup_remove_process)
                            if losetup_remove_process.returncode != 0:
                                LOG.debug("Failed to remove loop devices..." + loop_device)
                        LOG.debug("Removing sparse file " + sparse_file_path)
                        os.remove(sparse_file_path)
                    # remove mapper device
                    if os.path.exists(device_mapper):
                        LOG.debug("Removing device mapper " + device_mapper)
                        dm_setup_remove_process = utils.create_subprocess(['dmsetup', 'remove', device_mapper])
                        utils.call_subprocess(dm_setup_remove_process)
                        if dm_setup_remove_process.returncode != 0:
                            LOG.debug("Failed to remove /dev/mapper/" + image_id)
        except Exception as e:
            LOG.exception("Failed while cleanup :" + e.message)
            raise e

    # Function to rollback all the steps if decryption of image fails
    def __decrypt_rollback(self, image_id, instance_id):
        try:
            instance_link = os.path.join(self.pa_config['INSTANCES_DIR'], instance_id)
            instance_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id, instance_id)
            self.__cleanup(instance_link, instance_realpath, image_id)
        except Exception as e:
            LOG.exception("Failed while rollback process " + str(e.message))

    # Function to unlink, unmount ,removing key, sparse file, loop device, mapper device
    def delete(self, instance_path):
        try:
            if not os.path.exists(instance_path) or not os.path.islink(instance_path):
                LOG.error("Link " + instance_path + " doesnt exists.")
            else:
                instance_realpath = os.path.realpath(instance_path)
                image_id = instance_realpath.split("/")[3]
                LOG.debug("Image_id:" + image_id)
                self.__cleanup(instance_path, instance_realpath, image_id)
        except Exception as e:
            LOG.exception("Failed while deletion " + str(e.message))
            raise e

    # Function to decrypt image
    def decrypt(self, image_id, image, dek_url, instance_dir, root_disk_size_gb, instance_id):
        try:
            dec_dir = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id, Crypt.BASE_DIR)
            dec_file = os.path.join(dec_dir, image_id)
            key_path = os.path.join(self.pa_config['ENC_KEY_LOCATION'], image_id + Crypt.KEY_EXTN)
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
            sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], image_id)
            if not os.path.isfile(image):
                LOG.error("Failed to decrypt. " + image + ":file not found")
                raise Exception("Failed to decrypt as image " + image + " not found ")
            if utils.is_encrypted_file(image):
                if not os.path.exists(key_path) or os.path.getsize(key_path) != 256:
                    LOG.debug("send the decryption request to key server")
                    self.request_dek(dek_url, key_path)
                    LOG.debug("Key for decryption:" + key_path)
                if not os.path.isdir(self.pa_config['DISK_LOCATION']):
                    LOG.debug("Creating directory :" + self.pa_config['DISK_LOCATION'])
                    os.mkdir(self.pa_config['DISK_LOCATION'])
                format_device = False
                if not os.path.isfile(sparse_file_path):
                    LOG.debug("Creating sparse file: " + sparse_file_path)
                    self.__create_sparse_file(root_disk_size_gb, sparse_file_path)
                    format_device = True
                LOG.debug("Creating encrypted device at " + image_realpath)
                if not os.path.isdir(image_realpath):
                    LOG.debug("Creating directory:" + image_realpath)
                    os.makedirs(image_realpath)
                self.create_encrypted_device(image_id, image_realpath, sparse_file_path, key_path, format_device)
                if not os.path.isdir(dec_dir):
                    LOG.debug("Creating mount location base directory :" + dec_dir)
                    os.makedirs(dec_dir)
                if os.path.getsize(key_path) != 0:
                    if not os.path.isfile(dec_file):
                        make_tpm_proc = utils.create_subprocess(
                            [self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],
                             '-i', key_path, '-q', ta_config['binding.key.secret'], '-x'])
                        make_tpm_proc_1 = utils.create_subprocess(['openssl', 'enc', '-base64'],
                                                                  stdin=make_tpm_proc.stdout)
                        make_openssl_decrypt_proc = utils.create_subprocess(
                            ['openssl', 'enc', '-d', '-aes-128-ofb', '-in', image,
                             '-out', dec_file, '-pass', 'stdin'], make_tpm_proc_1.stdout)
                        utils.call_subprocess(make_openssl_decrypt_proc)
                        if make_openssl_decrypt_proc.returncode != 0:
                            LOG.error("Failed while decrypting image..Exit code = " + str(
                                make_openssl_decrypt_proc.returncode))
                            raise Exception("Failed while decrypting image")
                        else:
                            LOG.debug("Image decrypted successfully.")
                            os.remove(key_path)
                    else:
                        LOG.debug("Decrypted file already exists at " + dec_file)
                else:
                    LOG.error("Failed due to key file not found: " + key_path)
                    raise Exception("Failed due to key file not found")
                if utils.is_encrypted_file(dec_file) is False:
                    LOG.debug("Decrypted image : " + dec_file)
                    st = os.stat(image)
                    os.remove(image)
                    os.chown(dec_file, st.st_uid, st.st_gid)
                    utils.create_force_symlink(dec_file, image)
                else:
                    LOG.error("Failed while decrypting the image " + image)
                    raise Exception("Failed while decrypting the image")
            LOG.debug("Copy instance directory to encrypted device and create link")
            utils.copy_n_create_dir_link(instance_dir, os.path.join(image_realpath, instance_id))
            return dec_file
        except Exception as e:
            self.__decrypt_rollback(image_id, instance_id)
            LOG.exception("Failed while decrypting image " + str(e.message))
            raise e
