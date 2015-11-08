import os, shutil
import logging
import commons.utils as utils

class TrustPolicyStore:

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def getPolicy(self, image_id, pa_config):
        try:
            instances_dir = pa_config['INSTANCES_DIR']
            tarfile = os.path.join(instances_dir.strip(), '_base', image_id)
            dest = tarfile + '_temp'
            if not os.path.exists(tarfile):
                self.log.error("Image " + tarfile + " doesnot exists..")
                raise Exception("Image " + tarfile + " doesnot exists..")
            st = os.stat(tarfile)
            if utils.untar(tarfile, dest):
                self.log.debug("tarfile extracted ")
                trust_policy = None
                img_type=['img','vhd','raw','qcow2']
                for f in os.listdir(dest):
                    if f.endswith(".xml"):
                        trust_policy = tarfile + '.xml'
                        src = os.path.join(dest, f)
                        shutil.copy(src, trust_policy)
                        os.chmod(trust_policy, 0644)
                    if any(x in f for x in img_type):
                        src = os.path.join(dest, f)
                        shutil.move(src, tarfile)
                        os.chown(tarfile, st.st_uid, st.st_gid)
                shutil.rmtree(dest)
                return trust_policy
            else:
                trust_policy = tarfile + '.xml'
                if not os.path.exists(trust_policy):
                    self.log.error(tarfile + ".xml" + " not exists")
                    raise Exception(tarfile + ".xml" + " not exists")
                    #Throw error
                    #pass
                return trust_policy
        except Exception as e:
            self.log.exception("Failed while requesting policy : "+ str(e.message))
            raise e
