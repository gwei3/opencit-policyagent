import os, shutil
import logging
import commons.utils as utils
import swiftclient
import requests

class TrustPolicyStore:
    MODULE_NAME = 'policyagent'

    def __init__(self):
        self.log = logging.getLogger(TrustPolicyStore.MODULE_NAME)

    def getPolicy(self, args, pa_config):
        try:
            if not os.name == 'nt':
                image_id = args['base_image_id']
            else:
                image_id = args['image_id']
            instances_dir = pa_config['INSTANCES_DIR']
            tarfile = os.path.join(instances_dir.strip(), '_base', image_id)
            dest = tarfile + '_temp'
            policy_url = args['mtwilson_trustpolicy_location'].split(':',1)[1]
            if policy_url is None:
                self.log.error("Trustpolicy file location is not provided for image {}".format(image_id))
                raise Exception("Trustpolicy file location is not provided for image {}".format(image_id))
            if not os.path.exists(tarfile):
                self.log.error("Image " + tarfile + " doesnot exists..")
                raise Exception("Image " + tarfile + " doesnot exists..")
            #Here we get the permissions of the tarfile downloaded from glance
            st = os.stat(tarfile)
            trust_policy = tarfile + '.trustpolicy.xml'
            #Untar the file if it's a tar file
            if utils.untar(tarfile, dest):
                self.log.debug("tarfile extracted ")
                #After untar we move the xml and image file to _base dir, make sure the permissions are same as it was before untar
                #We also provide read access to trustpolicy for non root user as tagent runs as non root user.
                for f in os.listdir(dest):
                    if not f.endswith(".xml"):
                        src = os.path.join(dest, f)
                        shutil.move(src, tarfile)
                        os.chown(tarfile, st.st_uid, st.st_gid)
                shutil.rmtree(dest)
            #Get authentication token
            token = self.__request_auth_token(pa_config)
            #Download trustpolicy.xml from Swift
            self.__download_trustpolicy(policy_url, token, trust_policy)
            return trust_policy
        except Exception as e:
            self.log.exception("Failed while requesting policy : "+ str(e.message))
            raise e

    #Get authentication token
    def __request_auth_token(self, pa_config):
        self.log.debug("Getting authentication token")
        storage_url, token = swiftclient.client.get_auth(auth_url=pa_config['SWIFT_AUTH_URL'],
                                                         user="{}:{}".format(pa_config['RESELLER_ACCOUNT'],
                                                                             pa_config['RESELLER_USER']),
                                                         key=pa_config['RESELLER_PASSWORD'],
                                                         auth_version=pa_config['AUTH_VERSION'])
        self.log.debug("Authentication token received")
        return token

    def __download_trustpolicy(self, policy_url, token, trust_policy):
        #Send request to Swift to download trustpolicy
        headers = {'X-Auth-Token': token}
        req = requests.get(policy_url, headers=headers)
        #Write trustpolicy to disk
        if req.status_code == requests.codes.ok:
            with open(trust_policy, 'w') as trustpolicy_file:
                trustpolicy_file.write(req.content)
            os.chmod(trust_policy, 0644)
        else:
            self.log.error("Response code: {0}".format(req.status_code))
            self.log.error("Response: {0}".format(req.content))
            self.log.error("Failed to get the trustpolicy from {0}".format(policy_url))
            raise Exception("Failed to get the trustpolicy from {0}".format(policy_url))

