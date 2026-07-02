package EasyNAS::Controller::Nfs;
use lib '/easynas/lib/EasyNAS/Controller';
use Mojo::Base 'Mojolicious::Controller', -signatures;
use easynas;


my $msg;
my $result;
my $addon = get_addon_info("nfs");
my $service = ($addon->{service});
my %TEXT=get_lang_text($addon->{'name'});

sub view ($self) {
  if (!($self->session('is_auth'))) {
        $self->redirect_to('login');
  }
  my $action=$self->param('action');
  my $mount_dir=get_mount_dir();
  my $rc;
  $msg="";
  $result="";
  $self->stash(addon => $addon,
                TEXT =>\%TEXT);

##### nfson #####
 if (defined($action) && $action eq "nfson") {
  `/usr/bin/sudo /usr/bin/systemctl start rpcbind.service`;
  `/usr/bin/sudo /usr/bin/systemctl enable rpcbind.service`;
  `/usr/bin/sudo /usr/bin/systemctl start $service`;
  `/usr/bin/sudo /usr/bin/systemctl enable $service`;
  write_log($addon->{"name"},"INFO","NFS Service started");
 }

#### nfsoff #####
 if (defined($action) && $action eq "nfsoff") {
  `/usr/bin/sudo /usr/bin/systemctl stop $service`;
  `/usr/bin/sudo /usr/bin/systemctl disable $service`;
  `/usr/bin/sudo /usr/bin/systemctl stop rpcbind.service`;
  `/usr/bin/sudo /usr/bin/systemctl disable rpcbind.service`;
  write_log($addon->{"name"},"INFO","NFS Service stopped");
 }

##### create menu #####
 if (defined($action) && $action eq "create") {
  my %vol = vol_info();
  $self->stash(volumes => \%vol);
  $self->render(template => 'easynas/nfs_create');
  return;
 }

##### add share #####
 if (defined($action) && $action eq "add") {
  my $vol=$self->param("vol");
  my $per=$self->param("per");
  if (`/usr/bin/sudo /usr/bin/grep "$mount_dir/$vol " $addon->{config} 2>/dev/null`) {
   $result="fail";
   $msg=$TEXT{'nfs_exists'};
  }
  else {
   `/bin/echo "$mount_dir/$vol *($per,sync,no_subtree_check)" | /usr/bin/sudo /usr/bin/tee -a $addon->{config}`;
   $rc=system("/usr/bin/sudo /usr/sbin/exportfs -a >/dev/null");
   if (get_service_status($service)) {
    $rc=system("/usr/bin/sudo /usr/bin/systemctl restart $service >/dev/null");
   }
   write_log($addon->{"name"},"INFO","NFS share was added");
  }
 }

##### delete share #####
 if (defined($action) && $action eq "delete") {
  my $vol=$self->param("vol");
  my $fs=$self->param("fs");
  my $cmount_dir=substr($mount_dir,1);
  $rc=system("/usr/bin/sudo /usr/bin/sed -i '/.$cmount_dir.$fs.$vol /d' $addon->{config}");
  `/usr/bin/sudo /usr/sbin/exportfs -a`;
  if (get_service_status($service)) {
   `/usr/bin/sudo /usr/bin/systemctl reload $service`;
  }
  write_log($addon->{"name"},"INFO","NFS share was deleted");
 }

##### menu ######
  my $service_active=get_service_status($service);
  my @shares;
  my $path;
  my $fs;
  my $vol;
  my @nfs=`/usr/bin/sudo /usr/bin/grep $mount_dir $addon->{config} 2>/dev/null`;
  foreach (@nfs)
  {
   ($path,undef)=split(" ",$_);
   (undef,undef,$fs,$vol)=split("/",$path);
   push(@shares,{path=>$path,fs=>$fs,vol=>$vol});
  }
  $self->stash(service_active => $service_active,
	       shares => \@shares,
	       result => $result,
	       msg => $msg);
  $self->render(template => 'easynas/nfs');

}


1;
