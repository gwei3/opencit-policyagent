import os, shutil
import logging
import commons.utils as utils

#This module represents the store where trustpolicy is in the glance image tar file
class TrustPolicyStore:

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def getPolicy(self, args, config):
        try:
            tarfile = args['base_image']
            dest = tarfile + '_temp'
            if not os.path.exists(tarfile):
                self.log.error("Image " + tarfile + " doesnot exists..")
                raise Exception("Image " + tarfile + " doesnot exists..")
            #Here we get the permissions of the tarfile downloaded from glance
            st = os.stat(tarfile)
            #Untar the file if it's a tar file
            if utils.untar(tarfile, dest):
                self.log.debug("tarfile extracted ")
                trust_policy = None
                #After untar we move the xml and image file to _base dir, make sure the permissions are same as it was before untar
                #We also provide read access to trustpolicy for non root user as tagent runs as non root user.
                for f in os.listdir(dest):
                    if f.endswith(".xml"):
                        trust_policy = os.path.join(config['INSTANCES_DIR'], '_base', args['image_id']) + '.trustpolicy.xml'
                        src = os.path.join(dest, f)
                        shutil.copy(src, trust_policy)
                        if not os.name == 'nt':
                            os.chmod(trust_policy, 0644)
                    else:
                        src = os.path.join(dest, f)
                        shutil.move(src, tarfile)
                        if not os.name == 'nt':
                            os.chown(tarfile, st.st_uid, st.st_gid)
                shutil.rmtree(dest)
                return trust_policy
            else:
                #if the provided file is not a tar file then it was already downloaded and it's policy already exists
                trust_policy = os.path.join(config['INSTANCES_DIR'], '_base', args['image_id']) + '.trustpolicy.xml'
                if not os.path.exists(trust_policy):
                    self.log.error(trust_policy + " not exists")
                    raise Exception(trust_policy + " not exists")
                return trust_policy
        except Exception as e:
            self.log.exception("Failed while requesting policy : "+ str(e.message))
            raise e
