
import os, errno, stat
import shutil
import re
import requests
import logging

from commons.parse import ParseProperty
import commons.utils as utils

LOG = None
MODULE_NAME = 'policyagent'

class Crypt(object):
    AIK_PEM = "/aik.pem"
    KEY_EXTN = ".key"
    XML_EXTN = ".xml"
    BASE_DIR = "_base"
    LOST_FOUND = "lost+found"
    DEVICE_MAPPER = "/dev/mapper/"

    def __init__(self, **kwargs):
        pa_parse = ParseProperty()
        global LOG
        LOG = logging.getLogger(MODULE_NAME)
        if 'image' in kwargs:
            self.image_id = kwargs['image_id']
            self.image = kwargs['image']
            self.dek_url = kwargs['dek_url']
            self.instance_dir = kwargs['instance_dir']
            self.root_disk_size_gb = int(kwargs['root_disk_size_gb'])
            self.instance_id = kwargs['instance_id']
            self.pa_config = kwargs['config']
        else:
            self.instance_link = kwargs['instance_path']
            self.pa_config = kwargs['config']
        global ta_config
        ta_config = pa_parse.create_property_dict(self.pa_config['TRUST_AGENT_PROPERTIES'])

    # Function to verify if the file is encrypted or not
    def __openssl_encrypted_file(self, filename):
        try:
            with open(filename) as f:
                content = f.readline()
            return True if "Salted__" in content else False
        except Exception as e:
            LOG.exception("Failed while checking encryption of file " + filename)
            raise e

    # Function to create symbolic link
    def __force_symlink(self, target_filename, symbolic_filename):
        try:
            LOG.info("Creating link "+ symbolic_filename)
            #os.remove(symbolic_filename)
            os.symlink(target_filename, symbolic_filename)
        except Exception as e:
            raise e

    # Function to request key to KMS
    def __kms_request_key(self, aik_dir, key):
        LOG.debug("kms proxy ip address :" + self.pa_config['KMSPROXY_SERVER'])
        LOG.debug("kms jetty port :" + self.pa_config['KMSPROXY_SERVER_PORT'])
        try:
            if len(self.pa_config['KMSPROXY_SERVER_PORT']) and len(self.pa_config['KMSPROXY_SERVER']):
                if not os.path.isdir(self.pa_config['ENC_KEY_LOCATION']):
                    LOG.debug("Creating directory :" + self.pa_config['ENC_KEY_LOCATION'])
                    os.mkdir(self.pa_config['ENC_KEY_LOCATION'])
                proxies = {'http': 'http://' + self.pa_config['KMSPROXY_SERVER'] + ':' + self.pa_config['KMSPROXY_SERVER_PORT']}
                headers = {'Content-Type': 'application/x-pem-file', 'Accept': 'application/octet-stream'}
                with open(aik_dir + Crypt.AIK_PEM, 'rb') as f:
                    r = requests.post(self.dek_url, headers = headers, data = f,  proxies = proxies)
                if r.status_code == requests.codes.ok:
                    fd = open(key, 'w')
                    fd.write(r.content)
                    fd.close()
                else:
                    LOG.error("Failed to get the key " + key + " from the Key server.")
                    raise Exception("Failed to get the " + key + " from the Key server.")
            else:
                LOG.error("KMS configuration is not set in properties file.")
                raise Exception("KMS configuration is not set in properties file.")
        except Exception as e:
            LOG.exception("Failed while requesting key " + key + " from KMS :" + str(e.message))
            raise e

    # Function to create sparse file
    def __create_sparse_file(self, sparse_file_path):
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
            root_disk_size_kb = self.root_disk_size_gb*1024*1024
            LOG.info("Root disk size :" + str(root_disk_size_kb))
            LOG.info("Sparse file size :" + str(sparse_file_size_kb))
            if root_disk_size_kb > sparse_file_size_kb:
                LOG.error("The size of the root disk exceeds the allocated sparse file size ")
                raise Exception("The size of the root disk exceeds the allocated sparse file size ")
            size_in_bytes = sparse_file_size_kb*1024
            create_process_truncate = utils.create_subprocess(['truncate', '-s', str(size_in_bytes), str(sparse_file_path)])
            utils.call_subprocess(create_process_truncate)
            if create_process_truncate.returncode != 0:
                LOG.error("Failed to create sparse file " + sparse_file_path + "..Exit code = " + str(create_process_truncate.returncode))
                raise Exception("Failed to create sparse file")
            LOG.debug("Sparse file " + sparse_file_path + " created successfully.")
        except Exception as e:
            LOG.exception("Failed while creating sparse file: " + str(e.message))
            raise e

    # Function to create loop device, format and bind it, mount device mapper
    def __create_encrypted_device(self, image_realpath, sparse_file_path, key):
        device_mapper = os.path.join(Crypt.DEVICE_MAPPER, self.image_id)
        try:
            loop_dev = utils.get_loop_device(sparse_file_path)
            luks_format_proc_1 = utils.create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],\
                                                    '-i', key, '-q', ta_config['binding.key.secret'], '-x'])

            luks_format_proc_2 = utils.create_subprocess(['cryptsetup', '-v', '--batch-mode', 'luksFormat', '--key-file=-', loop_dev],\
                                                   stdin = luks_format_proc_1.stdout)
            call_luks_format_proc_2 = utils.call_subprocess(luks_format_proc_2)
            if luks_format_proc_2.returncode != 0:
                LOG.error("Failed while formatting loop device " + loop_dev + " ..exit code = " + str(call_luks_format_proc_2))
                raise Exception("Failed while formatting loop device " + loop_dev)
            LOG.debug("Loop device formatted successfully.")
            luks_open_proc_1 = utils.create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],\
                                                  '-i', key, '-q', ta_config['binding.key.secret'], '-x'])
            luks_open_proc_2 = utils.create_subprocess(['cryptsetup', '-v', 'luksOpen','--key-file=-',loop_dev, self.image_id],\
                                                 stdin = luks_open_proc_1.stdout)
            call_luks_open_proc_2 = utils.call_subprocess(luks_open_proc_2)
            if luks_open_proc_2.returncode != 0:
                LOG.error("Failed while key unbinding....Key =  " + key + " Loop device = " + loop_dev + "Exit code=" + str(call_luks_open_proc_2))
                raise Exception("Failed while key unbinding ..Key =  " + key + " Loop device = " + loop_dev)
            make_fs_status = utils.create_subprocess(['mkfs.ext4', '-v', device_mapper])
            utils.call_subprocess(make_fs_status)
            if make_fs_status.returncode != 0:
                LOG.error("Failed while creating ext4 filesystem " + device_mapper + " ..Exit code = " + str(make_fs_status.returncode))
                raise Exception("Failed while creating ext4 filesystem " + device_mapper)
            make_mount_process_status = utils.create_subprocess(['mount', '-t', 'ext4', device_mapper, image_realpath])
            utils.call_subprocess(make_mount_process_status)
            if make_mount_process_status.returncode != 0:
                LOG.error("Failed while mounting device mapper " + device_mapper + " ..Exit code = " + str(make_mount_process_status.returncode))
                raise Exception("Failed while mounting device mapper " + device_mapper)
            LOG.debug("Device mapper " + device_mapper + " mounted successfully")
        except Exception as e:
            LOG.exception("Failed while creating encrypted device: " + str(e.message))
            raise e

    # Function to create a link for instance
    def __create_instance_dir_link(self):
        try:
            LOG.info("Creating a link for instance ..")
            if self.instance_id is not None:
                dest = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id)
                if not os.path.exists(dest):
                    os.mkdir(dest)
                utils.copytree_with_permissions(self.instance_dir, os.path.join(dest, self.instance_id))
                shutil.rmtree(self.instance_dir)
                self.__force_symlink(os.path.join(dest, self.instance_id), self.instance_dir)
        except Exception as e:
            LOG.exception("Failed while creating instance link: "+ str(e.message))
            raise e

    # Function to request key for decryption
    def __request_dek(self, key):
        try:
            if os.path.exists(self.pa_config['XEN_TPM']) and os.access(self.pa_config['XEN_TPM'], os.X_OK):
                if os.path.exists(self.pa_config['AIK_BLOB_FILE']):
                    create_xen_tpm_proc = utils.create_subprocess([self.pa_config['XEN_TPM'],'--get_aik_pem',self.pa_config['AIK_BLOB_FILE'],\
                                                             '>','/tmp' + Crypt.AIK_PEM])
                    utils.call_subprocess(create_xen_tpm_proc)
                    if create_xen_tpm_proc.returncode != 0:
                        LOG.error("Failed while requesting key..Exit code = " + str(create_xen_tpm_proc.returncode))
                        raise Exception("Failed while requesting key ")
                else:
                    create_xen_tpm_proc = utils.create_subprocess([self.pa_config['XEN_TPM'],'--get_aik_pem','>','/tmp' + Crypt.AIK_PEM])
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
            self.__kms_request_key(aik_dir, key)
        except Exception as e:
            LOG.exception("Failed while requesting key :" + str(e.message))
            raise e

    #Function to cleanup
    def __cleanup(self, instance_link, instance_realpath, image_id):
        try:
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'],image_id + Crypt.KEY_EXTN)
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
                        os.remove(image_link + Crypt.XML_EXTN)
                    if os.path.ismount(image_realpath):
                        LOG.debug("Unmounting " + image_realpath)
                        make_umount_process_status = utils.create_subprocess(['umount', image_realpath])
                        utils.call_subprocess(make_umount_process_status)
                        if make_umount_process_status.returncode != 0:
                            LOG.debug("Failed to unmount " + image_realpath)
                    if os.path.exists(image_realpath):
                        LOG.debug("Removing image realpath " + image_realpath)
                        shutil.rmtree(image_realpath)
                    #remove sparse file
                    if os.path.exists(sparse_file_path):
                        LOG.debug("Finding loop device linked to sparse file " + sparse_file_path)
                        losetup_file_process = utils.create_subprocess(['losetup', '-j', sparse_file_path])
                        call_losetup_file_process = utils.call_subprocess(losetup_file_process)
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
                    if(os.path.exists(device_mapper)):
                        LOG.debug("Removing device mapper " + device_mapper )
                        dm_setup_remove_process = utils.create_subprocess(['dmsetup','remove', device_mapper])
                        utils.call_subprocess(dm_setup_remove_process)
                        if dm_setup_remove_process.returncode != 0:
                            LOG.debug("Failed to remove /dev/mapper/" + image_id)
        except Exception as e:
            LOG.exception("Failed while cleanup :" + e.message)
            raise e

    # Function to rollback all the steps if decryption of image fails
    def __decrypt_rollback(self):
        try:
            instance_link = os.path.join(self.pa_config['INSTANCES_DIR'], self.instance_id)
            instance_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id, self.instance_id)
            self.__cleanup(instance_link, instance_realpath, self.image_id)
        except Exception as e:
            LOG.exception("Failed while rollback process " + str(e.message))

    # Function to unlink, unmount ,removing key, sparse file, loop device, mapper device
    def delete(self):
        try:
            if not os.path.exists(self.instance_link) or not os.path.islink(self.instance_link):
                LOG.error("Link " + self.instance_link + " doesnt exists.")
            else:
                instance_realpath = os.path.realpath(self.instance_link)
                image_id = instance_realpath.split("/")[3]
                LOG.debug("Image_id:" + image_id)
                self.__cleanup(self.instance_link, instance_realpath, image_id)
        except Exception as e:
                LOG.exception("Failed while deletion " + str(e.message))
                raise e

    # Function to decrypt image
    def decrypt(self):
        try:
            dec_dir = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id, Crypt.BASE_DIR)
            dec_file = os.path.join(dec_dir, self.image_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'], self.image_id + Crypt.KEY_EXTN)
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id)
            sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], self.image_id)
            if not os.path.isfile(self.image):
                LOG.error("Failed to decrypt. " + self.image + ":file not found")
                raise Exception("Failed to decrypt as image " + self.image + " not found ")
            if self.__openssl_encrypted_file(self.image):
                if not os.path.exists(key) or os.path.getsize(key) != 256:
                    LOG.debug("send the decryption request to key server")
                    self.__request_dek(key)
                    LOG.debug("Key for decryption:" + key)
                if not os.path.isdir(self.pa_config['DISK_LOCATION']):
                    LOG.debug("Creating directory :" + self.pa_config['DISK_LOCATION'])
                    os.mkdir(self.pa_config['DISK_LOCATION'])
                if not os.path.isdir(image_realpath):
                    LOG.debug("Creating directory:" + image_realpath)
                    os.makedirs(image_realpath)
                if not os.path.isfile(sparse_file_path):
                    LOG.debug("Creating sparse file: " + sparse_file_path)
                    self.__create_sparse_file(sparse_file_path)
                    self.__create_encrypted_device(image_realpath, sparse_file_path, key)
                if not os.path.isdir(dec_dir):
                    LOG.debug("Creating mount location base directory :" + dec_dir)
                    os.makedirs(dec_dir)
                if (os.path.getsize(key) != 0) and not os.path.isfile(dec_file):
                    make_tpm_proc = utils.create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],\
                                                       '-i', key, '-q', ta_config['binding.key.secret'], '-x'])
                    make_tpm_proc_1 = utils.create_subprocess(['openssl', 'enc', '-base64'], stdin = make_tpm_proc.stdout)
                    call_tpm_proc = utils.call_subprocess(make_tpm_proc_1)
                    if make_tpm_proc_1.returncode != 0:
                        LOG.error("Failed while TPM_UNBIND_AES_KEY..Exit code=" + str(make_tpm_proc_1.returncode))
                        raise Exception("Failed while TPM_UNBIND_AES_KEY.")
                    pa_dek_key = call_tpm_proc
                    make_openssl_decrypt_proc = utils.create_subprocess(['openssl', 'enc', '-d', '-aes-128-ofb', '-in', self.image,\
                                                                   '-out', dec_file, '-pass', 'pass:' + pa_dek_key])
                    utils.call_subprocess(make_openssl_decrypt_proc)
                    if make_openssl_decrypt_proc.returncode != 0:
                        LOG.error("Failed while decrypting image..Exit code = " + str(make_openssl_decrypt_proc.returncode))
                        raise Exception("Failed while decrypting image")
                else:
                    LOG.error("Failed due to key or file not found : " + image_realpath + Crypt.BASE_DIR + self.image_id)
                    raise Exception("Failed due to key or file not found")
                if self.__openssl_encrypted_file(dec_file) is False:
                    LOG.debug("Decrypted image : " + dec_file)
                    st = os.stat(self.image)
                    os.remove(self.image)
                    os.chown(dec_file, st.st_uid, st.st_gid)
                    self.__force_symlink(dec_file, self.image)
                    self.__create_instance_dir_link()
                else:
                    LOG.error("Failed while decrypting the image "+self.image)
                    raise Exception("Failed while decrypting the image")
                return dec_file
            else:
                self.__create_instance_dir_link()
                return dec_file
        except Exception as e:
            self.__decrypt_rollback()
            LOG.exception("Failed while decrypting image " + str(e.message))
            raise e
