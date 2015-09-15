import os, errno, stat
import shutil
import re
import requests
import logging

#from pa_logging import PaLogging
from commons.pa_parse import ParseProperty
from commons.pa_utils import create_subprocess,call_subprocess,copytree_with_permissions

LOG = None
BASE_DIR = "_base"
LOST_FOUND = "lost+found"
DEVICE_MAPPER = "/dev/mapper/"

class PA_Crypt(object):

    def __init__(self, **kwargs):
        pa_parse = ParseProperty()
        global LOG
        LOG = logging.getLogger(__name__) 
        #global pa_config
        #pa_config = pa_parse.pa_create_property_dict(PA_CONFIG_PATH)
        if 'infile' in kwargs:
            self.image_id = kwargs['image_id']
            self.infile = kwargs['infile']
            self.dek_url = kwargs['dek_url']
            self.instance_dir = kwargs['instance_dir']
            self.root_disk_size_gb = int(kwargs['root_disk_size_gb'])
            self.instance_id = kwargs['instance_id']
            self.pa_config = kwargs['config']
        else:
            self.instance_link = kwargs['instance_path']
            self.pa_config = kwargs['config']
        global ta_config
        ta_config = pa_parse.pa_create_property_dict(self.pa_config['TRUST_AGENT_PROPERTIES'])

# Function to verify if the file is encrypted or not
    def __openssl_encrypted_file(self, filename):
        try:
            with open(filename) as f:
                content = f.readline()
            if "Salted__" in content:
                return True
            else:
                return False
        except Exception as e:
            LOG.exception("Failed while checking encryption status of file " +filename)
            raise e


# Function to create symbolic link
    def __force_symlink(self, target_filename, symbolic_filename):
        try:
            os.symlink(target_filename, symbolic_filename)
        except Exception as e:
            raise e

# Function to request key to KMS
    def __kms_request_key(self, aik_dir, key):
        LOG.debug("kms proxy ip address :"+self.pa_config['KMS_PROXY_SERVER'])
        LOG.debug("kms jetty port :"+self.pa_config['KMS_PROXY_SERVER_PORT'])
        try:
            if len(self.pa_config['KMS_PROXY_SERVER_PORT']) != 0 and len(self.pa_config['KMS_PROXY_SERVER']) != 0:
                if os.path.exists(self.pa_config['ENC_KEY_LOCATION']) and os.path.isdir(self.pa_config['ENC_KEY_LOCATION']):
                    LOG.debug("Requesting key from KMS")
                else:
                    LOG.debug("Creating directory :"+self.pa_config['ENC_KEY_LOCATION'])
                    os.mkdir(self.pa_config['ENC_KEY_LOCATION'])

                proxies = {'http': 'http://'+self.pa_config['KMS_PROXY_SERVER']+':'+self.pa_config['KMS_PROXY_SERVER_PORT']}
                headers={'Content-Type': 'application/x-pem-file', 'Accept': 'application/octet-stream'}
                with open(aik_dir+'/aik.pem', 'rb') as f:
                    r = requests.post(self.dek_url, headers=headers, data=f,  proxies=proxies)
                if r.status_code == requests.codes.ok :
                    fd = open(key, 'w')
                    fd.write(r.content)
                    fd.close()
                else:
                    LOG.error("Failed to get the Key from the Key server.")
                    raise Exception("Failed to get the Key from the Key server.")
        except Exception as e:
            LOG.exception("Failed while requesting key from KMS :"+str(e.message))
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
                    LOG.debug("The size of the sparse file in the properties file exceeds the available disk size")
                    LOG.debug("Allocating the available disk size to continue with the launch")
                    sparse_file_size_kb = available_space_kb
            root_disk_size_kb = self.root_disk_size_gb*1024*1024
            LOG.info("Root disk size :"+str(root_disk_size_kb))
            LOG.info("Sparse file size :"+str(sparse_file_size_kb))
            if root_disk_size_kb > sparse_file_size_kb:
                LOG.error("The size of the root disk exceeds the allocated sparse file size")
                raise Exception("The size of the root disk exceeds the allocated sparse file size")
            size_in_bytes=sparse_file_size_kb*1024
            create_process_truncate = create_subprocess(['truncate','-s', str(size_in_bytes), str(sparse_file_path)])
            call_subprocess(create_process_truncate)
            if create_process_truncate.returncode != 0:
                LOG.error("The sparse file creation status"+str(create_process_truncate.returncode))
                raise Exception("Sparse file creation failed.")
            LOG.debug("Sparse file created successfully.")
        except Exception as e:
            LOG.exception("Failed while creating sparse file :"+str(e.message))
            raise e

# Function to create loop device, format and bind it, mount device mapper
    def __create_loop_device(self, image_realpath, sparse_file_path, key):
        device_mapper = os.path.join(DEVICE_MAPPER, self.image_id)
        try:
            make_proc = create_subprocess(['losetup', '--find'], None)
            loop_dev = call_subprocess(make_proc)
            if loop_dev is None:
                LOG.debug("Requires additional loop device for use")
                count=0
                for f in os.listdir('/dev/'):
                    if f.startswith('loop'):
                        num = f[4:]
                        if re.match("^([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])$",num) is not None:
                            count = count+1
                device_name = '/dev/loop'+str(count)
                device = os.makedev(7,count)
                os.mknod(device_name, 0660 | stat.S_ISBLK, device)
                make_proc = create_subprocess(['losetup','--find'])
                loop_dev = call_subprocess(make_proc)
            if loop_dev is not None:
                make_proc = create_subprocess(['losetup', loop_dev, sparse_file_path])
                call_subprocess(make_proc)
                if make_proc.returncode != 0:
                    LOG.error("Failed while mounting loop device")
                    raise Exception("Failed while mounting loop device")
            else:
                LOG.error("No loop device available")
                raise Exception("No loop device available")
        except Exception as e:
            LOG.exception("Failed while creating or mounting loop device :"+str(e.message))
            raise e
        try:
            luks_format_proc_1 = create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'], '-i', key, '-q', ta_config['binding.key.secret'], '-x'])

            luks_format_proc_2 = create_subprocess(['cryptsetup', '-v', '--batch-mode', 'luksFormat', '--key-file=-', loop_dev], stdin=luks_format_proc_1.stdout)
            call_luks_format_proc_2 = call_subprocess(luks_format_proc_2)
            if luks_format_proc_2.returncode != 0 :
                LOG.error("Status of luks_format="+str(call_luks_format_proc_2))
                raise Exception("Failed while formatting loop device")
            LOG.debug("Loop device formatted successfully.")
        except Exception as e:
            LOG.exception("Failed while formatting loop device :"+str(e.message))
            raise e
        try:
            luks_open_proc_1 = create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'], '-i', key, '-q', ta_config['binding.key.secret'], '-x'])
            luks_open_proc_2 = create_subprocess(['cryptsetup', '-v', 'luksOpen','--key-file=-',loop_dev, self.image_id], stdin=luks_open_proc_1.stdout)
            call_luks_open_proc_2 = call_subprocess(luks_open_proc_2)
            if luks_open_proc_2.returncode != 0:
                LOG.error("luksOpen_status error:"+str(call_luks_open_proc_2))
                raise Exception("Failed while luksOpen")
        except Exception as e:
            LOG.exception("Failed while luksOpen :"+str(e.message))
            raise e
        try:
            make_fs_status = create_subprocess(['mkfs.ext4', '-v', device_mapper])
            call_subprocess(make_fs_status)
            if make_fs_status.returncode != 0:
                LOG.error("Status of mkfs:"+str(make_fs_status.returncode))
                raise Exception("Failed while ext4")
        except Exception as e:
            LOG.exception("Failed while ext4 :"+str(e.message))
            raise e
      #Mount device over mount location identified by <image_uuid>
        try:
            make_mount_process_status = create_subprocess(['mount', '-t', 'ext4', device_mapper, image_realpath])
            call_subprocess(make_mount_process_status)
            if make_mount_process_status.returncode != 0:
                LOG.error("Failed while mount..Status :"+str(make_mount_process_status.returncode))
                raise Exception("Failed while mounting device mapper")
            LOG.debug("Device mapper mounted successfully")
        except Exception as e:
            LOG.exception("Failed while mounting device mapper :"+str(e.message))
            raise e

# Function to create a link for instance
    def __create_instance_dir_link(self):
        try:
            if self.instance_id is not None:
                dest = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id)
                if not os.path.exists(dest):
                    os.mkdir(dest)
                copytree_with_permissions(self.instance_dir, os.path.join(dest, self.instance_id))
                #shutil.copytree(self.instance_dir, os.path.join(dest, self.instance_id))
                shutil.rmtree(self.instance_dir)
                self.__force_symlink(os.path.join(dest, self.instance_id), self.instance_dir)
        except Exception as e:
            LOG.exception("Failed while creating instance dir link."+str(e.message))
            raise e

# Function to request key for decryption
    def __pa_request_dek(self, key):
        try:
            if os.path.exists(self.pa_config['XEN_TPM']) and os.access(self.pa_config['XEN_TPM'], os.X_OK):
                if os.path.exists(self.pa_config['AIK_BLOB_FILE']):
                    create_xen_tpm_proc = create_subprocess([self.pa_config['XEN_TPM'],'--get_aik_pem',self.pa_config['AIK_BLOB_FILE'],'>','/tmp/aik.pem'])
                    call_subprocess(create_xen_tpm_proc)
                    if create_xen_tpm_proc.returncode != 0:
                        LOG.error("Failed while requesting key..status:"+str(create_xen_tpm_proc.returncode))
                        raise Exception("Failed while requesting key")
                    else:
                        LOG.debug("Key request executed successfully.")
                else:
                    create_xen_tpm_proc = create_subprocess([self.pa_config['XEN_TPM'],'--get_aik_pem','>','/tmp/aik.pem'])
                    call_subprocess(create_xen_tpm_proc)
                    if create_xen_tpm_proc.returncode != 0:
                        LOG.error("Failed while requesting key..status:"+str(create_xen_tpm_proc.returncode))
                        raise Exception("Failed while requesting key")
                    else:
                        LOG.debug("Key request executed successfully.")
                aik_dir = "/tmp"
            else:
                aik_dir = self.pa_config['TRUST_AGENT_CONFIG_PATH']
            if not os.path.exists(aik_dir+"/aik.pem") or not os.path.isfile(aik_dir+"/aik.pem"):
                LOG.error("Error: Missing AIK Public Key")
                raise Exception("Missing AIK Public Key")
            self.__kms_request_key(aik_dir, key)
        except Exception as e:
            LOG.exception("Failed while requesting key :")
            raise e

# Function to rollback all the steps if decryption of image fails
    def __pa_decrypt_rollback(self):
        try:
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id)
            sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], self.image_id)
            image_link = os.path.join(self.pa_config['INSTANCES_DIR'], BASE_DIR, self.image_id)
            instance_link = os.path.join(self.pa_config['INSTANCES_DIR'], self.instance_id)
            instance_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id, self.instance_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'],self.image_id+".key")
            device_mapper = os.path.join(DEVICE_MAPPER, self.image_id)

            if os.path.exists(key):
                os.remove(key)

            if os.path.exists(instance_link):
                if os.path.islink(instance_link):
                    os.unlink(instance_link)
                shutil.rmtree(instance_link)

            if os.path.exists(instance_realpath):
                shutil.rmtree(instance_realpath)

            if os.path.exists(image_link):
                if os.path.islink(image_link):
                    os.unlink(image_link)
                os.remove(image_link)

            if os.path.exists(image_link+".xml") and os.path.isfile(image_link+".xml"):
                os.remove(image_link+".xml")

            if os.path.ismount(image_realpath):
                make_umount_process_status = create_subprocess(['umount', image_realpath])
                call_subprocess(make_umount_process_status)
                if make_umount_process_status.returncode != 0:
                    LOG.debug("Failed to unmount")
                else:
                    LOG.debug("Unmount successfully.")

            if os.path.exists(image_realpath):
                 shutil.rmtree(image_realpath)

       
            if os.path.exists(sparse_file_path):
                losetup_file_process = create_subprocess(['losetup', '-j', sparse_file_path])
                call_losetup_file_process = call_subprocess(losetup_file_process)
                if losetup_file_process.returncode != 0 or call_losetup_file_process == '':
                    LOG.debug("No loop device")
                else:
                    loop_device = call_losetup_file_process.split(":")[0]
                    losetup_remove_process = create_subprocess(['losetup', '-d', loop_device])
                    call_subprocess(losetup_remove_process)
                    if losetup_remove_process.returncode != 0 :
                        LOG.debug("Failed to detach loop devices...")
                os.remove(sparse_file_path)
            if os.path.exists(device_mapper):
                dm_setup_remove_process = create_subprocess(['dmsetup', 'remove', device_mapper])
                call_subprocess(dm_setup_remove_process)
                if dm_setup_remove_process.returncode != 0:
                    LOG.debug("Failed to remove /dev/mapper/"+self.image_id)
        except Exception as e:
            LOG.exception("Failed to rollback "+str(e.message))


# Function to unlink, unmount ,removing key, sparse file, loop device, mapper device
    def pa_delete(self):
        try:
            if not os.path.exists(self.instance_link) or not os.path.islink(self.instance_link):
                LOG.error("Link doesnt exists.")
            else:
                instance_realpath = os.path.realpath(self.instance_link)
                LOG.debug("Remove link")
                os.unlink(self.instance_link)
                image_id = instance_realpath.split("/")[3]
                LOG.debug("Image_id:"+image_id)
                shutil.rmtree(instance_realpath)
                image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
                sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], image_id)
                image_link = os.path.join(self.pa_config['INSTANCES_DIR'], BASE_DIR, image_id)
                key = os.path.join(self.pa_config['ENC_KEY_LOCATION'],image_id+".key")
                device_mapper = os.path.join(DEVICE_MAPPER,image_id)
                list_dirs = os.listdir(image_realpath)

                if os.path.exists(key):
                    LOG.debug("Remove key")
                    os.remove(key)
                # remove _base and lost+found dir from list
                if BASE_DIR in list_dirs:
                    list_dirs.remove(BASE_DIR)

                if LOST_FOUND in list_dirs:
                    list_dirs.remove(LOST_FOUND)

                if len(list_dirs) == 0:
                    if os.path.islink(image_link):
                        os.unlink(image_link)
                        os.remove(image_link+".xml")
                        LOG.debug("Removed link:"+image_link+"and "+image_link+".xml")
                    if os.path.ismount(image_realpath):
                        make_umount_process_status = create_subprocess(['umount', image_realpath])
                        call_subprocess(make_umount_process_status)
                        if make_umount_process_status.returncode != 0:
                            LOG.debug("Failed to unmount")
                        else:
                            LOG.debug("Unmount successfully.")
                    shutil.rmtree(image_realpath)
                    #remove sparse file
                    LOG.debug("Remove sparse file")
                    if os.path.exists(sparse_file_path):
                        losetup_file_process = create_subprocess(['losetup', '-j', sparse_file_path])
                        call_losetup_file_process = call_subprocess(losetup_file_process)
                        if losetup_file_process.returncode != 0:
                            LOG.debug("Failed to find linked loop device.")
                        else:
                            loop_device = call_losetup_file_process.split(":")[0]
                            LOG.debug("Detach loop device")
                            losetup_remove_process = create_subprocess(['losetup', '-d', loop_device])
                            call_subprocess(losetup_remove_process)
                            if losetup_remove_process.returncode != 0:
                                LOG.debug("Failed to remove loop devices...")
                        os.remove(sparse_file_path)
                    LOG.debug("Remove device mapper")
                    dm_setup_remove_process = create_subprocess(['dmsetup','remove', device_mapper])
                    call_subprocess(dm_setup_remove_process)
                    if dm_setup_remove_process.returncode != 0:
                        LOG.debug("Failed to remove /dev/mapper/"+image_id)
        except Exception as e:
                LOG.exception("Failed while delete ")
                raise e

# Function to decrypt image
    def pa_decrypt(self):
        try:
            dec_dir = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id, BASE_DIR)
            dec_file = os.path.join(dec_dir, self.image_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'], self.image_id+".key")
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], self.image_id)
            sparse_file_path = os.path.join(self.pa_config['DISK_LOCATION'], self.image_id)

            if os.path.exists(key) and os.path.isfile(key):
                os.remove(key)

            if os.path.exists(self.infile) and os.path.isfile(self.infile):
                LOG.debug("File exists :"+self.infile)
            else:
                LOG.error("Failed to decrypt. "+self.infile+":file not found")
                #self.__pa_decrypt_rollback()
                raise Exception("Failed to decrypt.File not found.")

            if self.__openssl_encrypted_file(self.infile):
                if not os.path.exists(key) or os.path.getsize(key) != 256:
                    LOG.debug("send the decryption request to key server")
                    self.__pa_request_dek(key)
                    LOG.debug("Key for decryption:"+key)

                if os.path.exists(self.pa_config['DISK_LOCATION']) and os.path.isdir(self.pa_config['DISK_LOCATION']):
                    LOG.debug("Disk location exists:"+self.pa_config['DISK_LOCATION'])
                else:
                    LOG.debug("Creating directory :"+self.pa_config['DISK_LOCATION'])
                    os.mkdir(self.pa_config['DISK_LOCATION'])

                if os.path.exists(image_realpath) and os.path.isdir(image_realpath):
                    LOG.debug("Mount location exists:"+image_realpath)
                else:
                    LOG.debug("Creating directory:"+image_realpath)
                    os.makedirs(image_realpath)

                if os.path.exists(sparse_file_path) and os.path.isfile(sparse_file_path):
                    LOG.debug("Sparse file already exists:"+sparse_file_path)
                else:
                    LOG.debug("Creating sparse file:")
                    self.__create_sparse_file(sparse_file_path)
                    self.__create_loop_device(image_realpath, sparse_file_path, key)

                if os.path.exists(dec_dir) and os.path.isdir(dec_dir):
                    LOG.debug("mount location _base dir already exits:"+dec_dir)
                else:
                    LOG.debug("Creating mount location base directory :"+dec_dir)
                    os.makedirs(dec_dir)

                if (os.path.getsize(key) != 0) and not os.path.isfile(dec_file):
                    make_tpm_proc = create_subprocess([self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'], '-i', key, '-q', ta_config['binding.key.secret'], '-x'])
                    make_tpm_proc_1 = create_subprocess(['openssl', 'enc', '-base64'], stdin=make_tpm_proc.stdout)
                    call_tpm_proc = call_subprocess(make_tpm_proc_1)
                    if make_tpm_proc_1.returncode != 0:
                        LOG.error("Failed while TPM_UNBIND_AES_KEY..status:"+str(make_tpm_proc_1.returncode))
                        #self.__pa_decrypt_rollback()
                        raise Exception("Failed while TPM_UNBIND_AES_KEY.")
                    pa_dek_key = call_tpm_proc

                    make_openssl_decrypt_proc = create_subprocess(['openssl', 'enc', '-d', '-aes-128-ofb', '-in', self.infile, '-out', dec_file, '-pass', 'pass:' + pa_dek_key])
                    call_subprocess(make_openssl_decrypt_proc)
                    if make_openssl_decrypt_proc.returncode !=0 :
                        LOG.error("Failed while decrypting image..status:"+str(make_openssl_decrypt_proc.returncode))
                        #self.__pa_decrypt_rollback()
                        raise Exception("Failed while decrypting image")
                    LOG.debug("Decryption of image is done.")
                else:
                    LOG.error("Failed due to key or file not found : " + image_realpath + "/_base/" + self.image_id)
                    #self.__pa_decrypt_rollback()
                    raise Exception("Failed due to key or file not found")

                if self.__openssl_encrypted_file(dec_file) is False:
                    LOG.debug("Decrypted image:"+self.image_id)
                    st = os.stat(self.infile)
                    os.remove(self.infile)
                    os.chown(dec_file, st.st_uid, st.st_gid)

                    self.__force_symlink(dec_file, self.infile)
                    self.__create_instance_dir_link()
                else:
                    LOG.error("Failed to decrypt the image "+self.infile)
                    #self.__pa_decrypt_rollback()
                    raise Exception("Failed to decrypt the image")
                return dec_file
            else:
                self.__create_instance_dir_link()
                return dec_file
        except Exception as e:
            #self.__pa_decrypt_rollback()
            LOG.exception("Failed while decrypting image "+str(e.message))
            raise e






