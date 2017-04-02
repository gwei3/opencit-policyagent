import os
import shutil
import requests
import logging
import time
from commons.parse import ParseProperty
import commons.utils as utils
from subprocess import PIPE

LOG = None
ta_config = None
MODULE_NAME = 'policyagent'


class WinCrypt(object):
    AIK_PEM = "aik.pem"
    KEY_EXTN = ".key"
    XML_EXTN = ".xml"
    BASE_DIR = "_base"
    DEVICE_MAPPER = "/dev/mapper/"

    def __init__(self, config):
        """
        :type config: PolicyAgent configuration object
        """
        pa_parse = ParseProperty()
        global LOG
        LOG = logging.getLogger(MODULE_NAME)
        self.pa_config = config
        #TA_PROP_FILE = "trustagent" + ((str)((int)(time.time()))) + ".properties"
        #decrypt_tagent_prop_process = utils.create_subprocess(['tagent', 'export-config', TA_PROP_FILE])
        #utils.call_subprocess(decrypt_tagent_prop_process)
        #if decrypt_tagent_prop_process.returncode != 0:
        #   LOG.error("Failed to decrypt trustagent properties file. Exit code = " + str(decrypt_tagent_prop_process.returncode))
        #    raise Exception("Failed to decrypt trustagent properties file.")
        global ta_config
        ta_config = pa_parse.create_property_dict(config['TRUST_AGENT_PROPERTIES'])
        #clean the temporary file after readng it
        #os.remove(TA_PROP_FILE)

    # Function to request key to KMS
    def __kms_request_key(self, aik_dir, dek_url, key_path):
        LOG.debug("kms proxy ip address :" + self.pa_config['KMSPROXY_SERVER'])
        LOG.debug("kms jetty port :" + self.pa_config['KMSPROXY_SERVER_PORT'])
        try:
            if len(self.pa_config['KMSPROXY_SERVER_PORT']) and len(self.pa_config['KMSPROXY_SERVER']):
                if not os.path.isdir(self.pa_config['ENC_KEY_LOCATION']):
                    LOG.debug("Creating directory :" + self.pa_config['ENC_KEY_LOCATION'])
                    os.mkdir(self.pa_config['ENC_KEY_LOCATION'])
                proxies = {'http': 'http://' + self.pa_config['KMSPROXY_SERVER'] + ':' + self.pa_config[
                    'KMSPROXY_SERVER_PORT']}
                headers = {'Content-Type': 'application/x-pem-file', 'Accept': 'application/octet-stream'}
                with open(aik_dir + WinCrypt.AIK_PEM, 'rb') as f:
                    r = requests.post(dek_url, headers=headers, data=f, proxies=proxies)
                if r.status_code == requests.codes.ok:
                    fd = open(key_path, 'w')
                    fd.write(r.content)
                    fd.close()
                    shutil.copy(key_path, "C:\\mykey.key")
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

    # Function to request key for decryption
    def request_dek(self, dek_url, key_path):
        try:
            aik_dir = self.pa_config['TRUST_AGENT_CONFIG_PATH']
            if not os.path.isfile(os.path.join(aik_dir, WinCrypt.AIK_PEM)):
                LOG.error("Error: Missing AIK Public Key " + aik_dir + WinCrypt.AIK_PEM)
                raise Exception("Missing AIK Public Key " + aik_dir + WinCrypt.AIK_PEM)
            self.__kms_request_key(aik_dir, dek_url, key_path)
        except Exception as e:
            LOG.exception("Failed while requesting key :" + str(e.message))
            raise e

    # Function to cleanup
    def __cleanup(self, instance_link, instance_realpath, image_id):
        try:
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
            key = os.path.join(self.pa_config['ENC_KEY_LOCATION'], image_id + WinCrypt.KEY_EXTN)
            image_link = os.path.join(self.pa_config['INSTANCES_DIR'], WinCrypt.BASE_DIR, image_id)
            LOG.info("Starting clean_up :")
            LOG.info("Instance symbolic link = " + instance_link)
            LOG.info("Instance realpath = " + instance_realpath)
            LOG.info("Image symbolic link = " + image_link)
            LOG.info("Image realpath = " + image_realpath)
            LOG.info("Key = " + key)
            if os.path.exists(instance_link) and (os.path.getsize(instance_link) == 0):
                LOG.debug("Removing symbolic link " + instance_link)
                os.remove(instance_link)
            if os.path.exists(instance_realpath):
                LOG.debug("Removing instance realpath " + instance_realpath)
                shutil.rmtree(instance_realpath)
            if os.path.exists(instance_link):
                LOG.debug("Removing instance directory " + instance_link)
                shutil.rmtree(instance_link)
            if os.path.exists(image_realpath):
                list_dirs = os.listdir(image_realpath)
                # remove _base dir from list
                if WinCrypt.BASE_DIR in list_dirs:
                    list_dirs.remove(WinCrypt.BASE_DIR)
                if len(list_dirs) == 0:
                    if os.path.exists(key):
                        LOG.debug("Removing key " + key)
                        os.remove(key)
					# Islink alternative in windows
                    if os.path.exists(image_link) and (os.path.getsize(image_link) == 0):
                        LOG.debug("Removing image link " + image_link + "and " + image_link + WinCrypt.XML_EXTN)
                        os.remove(image_link)
                        os.remove(image_link + '.trustpolicy' + WinCrypt.XML_EXTN)
                    if os.path.exists(image_realpath):
                        LOG.debug("Removing image realpath " + image_realpath)
                        shutil.rmtree(image_realpath)
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
            if not os.path.exists(instance_path) or (os.path.getsize(instance_path) != 0):
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
            dec_dir = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id, WinCrypt.BASE_DIR)
            dec_file = os.path.join(dec_dir, image_id)
            key_path = os.path.join(self.pa_config['ENC_KEY_LOCATION'], image_id + WinCrypt.KEY_EXTN)
            image_realpath = os.path.join(self.pa_config['MOUNT_LOCATION'], image_id)
            if not os.path.isfile(image):
                LOG.error("Failed to decrypt. " + image + ":file not found")
                raise Exception("Failed to decrypt as image " + image + " not found ")
            if utils.is_encrypted_file(image):
                if not os.path.exists(key_path) or os.path.getsize(key_path) != 256:
                    LOG.debug("send the decryption request to key server")
                    self.request_dek(dek_url, key_path)
                    LOG.debug("Key for decryption:" + key_path)
                if not os.path.isdir(image_realpath):
                    LOG.debug("Creating directory:" + image_realpath)
                    os.makedirs(image_realpath)
                if not os.path.isdir(dec_dir):
                    LOG.debug("Creating mount location base directory :" + dec_dir)
                    os.makedirs(dec_dir)
                if os.path.getsize(key_path) != 0:
                    if not os.path.isfile(dec_file):
                        os.chdir('C:\Program Files (x86)\Intel\Policy Agent\\bin')
                        make_tpm_proc = utils.create_subprocess(
                            [self.pa_config['TPM_UNBIND_AES_KEY'], '-k', self.pa_config['PRIVATE_KEY'],
                             '-i', key_path, '-q', ta_config['binding.key.secret'], '-b', self.pa_config['PRIVATE_KEY_BLOB']])
                        output = utils.call_subprocess(make_tpm_proc)
                        if make_tpm_proc.returncode != 0:
                            LOG.error("Failed while unbinding key. Exit code = " + str(
                            make_tpm_proc.returncode))
                            raise Exception("Failed while unbinding key.")
                        dec_key = output[0]
                        make_tpm_proc_1 = utils.create_subprocess(['python', '-m', 'base64', '-e'],
                                                                  stdin=PIPE)
                        output = utils.call_subprocess(make_tpm_proc_1, dec_key)
                        if make_tpm_proc_1.returncode != 0:
                            LOG.error("Failed while encoding key. Exit code = " + str(
                                make_tpm_proc_1.returncode))
                            raise Exception("Failed while encoding key.")
                        dec_key = output[0]
                        with open(image, 'rb') as in_file, open(dec_file, 'wb') as out_file:
                            utils.aes_decrypt(in_file, out_file, dec_key)
                    else:
                        LOG.debug("Decrypted file already exists at " + dec_file)
                else:
                    LOG.error("Failed due to key file not found: " + key_path)
                    raise Exception("Failed due to key file not found")
                if utils.is_encrypted_file(dec_file) is False:
                    LOG.debug("Decrypted image : " + dec_file)
                    #st = os.stat(image)
                    os.remove(image)
                    #os.chown(dec_file, st.st_uid, st.st_gid)
                    utils.create_force_symlink(dec_file, image)
                else:
                    LOG.error("Failed while decrypting the image " + image)
                    raise Exception("Failed while decrypting the image")
            #os.mkdir(instance_dir)
            #LOG.debug("Copy instance directory to encrypted device and create link")
            #utils.copy_n_create_dir_link(instance_dir, os.path.join(image_realpath, instance_id))
            return dec_file
        except Exception as e:
            self.__decrypt_rollback(image_id, instance_id)
            LOG.exception("Failed while decrypting image " + str(e.message))
            raise e
