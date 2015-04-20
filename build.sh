#!/bin/bash

# NOTE: this script must be run from the dcg_security-policyagent folder as current directory
# NOTE: this build.sh script will be replaced by an ant/maven combination, and a lot of changes to the
#       build itself instead of using the same .tar.gz

mkdir -p packages/mtwilson-policyagent/target

tar cfz packages/mtwilson-policyagent/target/mtwilson-policyagent.tgz linux nova-compute xen
