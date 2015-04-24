
apt-get install xmlstarlet
status=`echo $?`
echo "$status"
dir=/opt/policyagent/configuration/

if [ ! -d $dir ]; then
   mkdir -p $dir
fi

cp ./policyagent.properties $dir
cp ./policyagent /usr/local/bin/policyagent
chmod +x /usr/local/bin/policyagent

rm -f /var/log/policyagent.log
touch /var/log/policyagent.log
chmod 666  /var/log/policyagent.log
rm /var/lib/nova/instances/_base/*

chmod +x ./Validate.java
javac ./Validate.java 
mv ./Validate*.class /usr/local/bin/
chmod +x /usr/local/bin/Validate*
chown nova:nova /usr/local/bin/Validate*
