#!/usr/bin/perl

use strict;

use lib '/home/wwwadmin/lib/perl';

use CGI;
use JSON;
use LWP::UserAgent;
use File::Spec;

use File::Slurp;
use IO::File;
use DateTime;
use Data::Dumper;

use Const;
use GymConfig;

my %ALLOWED_GYMIDS = map { $_ => $GymConfig::GYMS->{ $_ }->{subdomain} } keys %$GymConfig::GYMS;

my %DAY_OFFSET = map { $_ => $GymConfig::GYMS->{ $_ }->{day_offset} } keys %$GymConfig::GYMS;

my %LOCATION_REMAPPING = map { $_ => $GymConfig::GYMS->{ $_ }->{location_remapping} } keys %$GymConfig::GYMS;

my %TITLE_REMAPPING = map { $_ => $GymConfig::GYMS->{ $_ }->{title_remapping} } keys %$GymConfig::GYMS;

my %allowed_periods = ( 'day'  => 1
                       ,'week' => 1
                     );

my $URLBASE = 'sites.zenplanner.com/api/calendar.cfm';
my $USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9B179 Safari/7534.48.3';
my $CACHE_DIR = "$Const::HOMEDIR/cachedContent/";

my $MAX_DAYS_FORWARD = 0;

my $DEFAULT_CACHE_TIMEOUT_SECS = 2 * 60 * 60;  # 2 hours

my $cgi = CGI->new();

my $gym_id_raw = $cgi->param('gymId');

my $gym_id;
if ( defined $gym_id_raw and $gym_id_raw =~ m/^([A-Z\-\_0-9]{1,20})/ ) {
    $gym_id = $1;
} else {
    die "no gymId specified";
}

my $gym_subdomain;
unless ( $gym_subdomain = $ALLOWED_GYMIDS{ $gym_id } ) {
  die "gymId '$gym_id' unsupported";
}

my $raw_start_date = $cgi->param('startDate');

my ( $year, $month, $day );
if ( $raw_start_date =~ m/^(20\d{2})(\d{2})(\d{2})$/ ) {
    ( $year, $month, $day ) = ( $1, $2, $3 );
} else {
    die "bad 'startDate' specified";
}

my $raw_period = $cgi->param('period') || 'day';

my $period;
if ( $raw_period =~ m/^(day|week)$/ ) {
    $period = $1;
} else {
    die "bad 'period' specified";
}

my $raw_tz = $cgi->param('timeZone');

my $tz;
if ( $raw_tz =~ m|^(\w{1,40}/\w{1,40}(\w{1,40}))| ) {
    $tz = $1;
} else {
    die "bad 'timeZone' specified";
}

my $now = DateTime->now( time_zone => $tz );
my $limit_date = DateTime->new( year      => $now->year
                               ,month     => $now->month
                               ,day       => $now->day
                               ,time_zone => $tz
                              );
$limit_date->add( days => $MAX_DAYS_FORWARD );

my $start_date = DateTime->new( year      => $year
                  			       ,month     => $month
                   	 		       ,day       => $day
                  			       ,time_zone => $tz
                              );

my $cache_date = "$year$month$day";
my %native_outbound_content = ( date     => $cache_date
                               ,version  => 0.1
                              );

# check if we are past the date limit
if ( $MAX_DAYS_FORWARD and DateTime->compare( $start_date, $limit_date ) > 0 ) {
    print $cgi->header();
    print encode_json( \%native_outbound_content );
    exit(0);
}

# not totally clear why this date offset thing is needed
my $day_offset = $DAY_OFFSET{ $gym_id };
die "no day_offset configured for gym '$gym_id'" unless ( defined $day_offset );
$start_date->add(days => $day_offset);

my $start_epoch = $start_date->epoch;

my $offset = 1 * 24 * 60 * 60; # one day
$offset *= 7 if ( $period eq 'week' );

my $end_epoch = $start_epoch + $offset;

my $cache_path = File::Spec->catfile( $CACHE_DIR, $gym_id, "schedule", "${cache_date}_${period}" );

if ( -e $cache_path ) { 

    my $modtime_secs = (-M $cache_path) * 24 * 60 * 60; # seconds ago file was modified
    
    if ( $modtime_secs < $DEFAULT_CACHE_TIMEOUT_SECS ) {

      my $content = File::Slurp::read_file( $cache_path );
      print $cgi->header();
      print $content;
    	exit(0);
    }
}

my $ua = LWP::UserAgent->new();
#$ua->agent( $USER_AGENT );

my $url = "https://${gym_subdomain}.${URLBASE}?start=${start_epoch}&end=${end_epoch}";

my $req = HTTP::Request->new(GET => $url);
my $res = $ua->request($req);

if ( $res->is_success ) {

    my $content = decode_json( $res->content );

    my @filtered_content;
    foreach my $entry ( @$content ) {

        my $mapped_location = $LOCATION_REMAPPING{ $gym_id }->{ $entry->{location} };
        $mapped_location ||= $entry->{location};

        my $mapped_title = $TITLE_REMAPPING{ $gym_id }->{ $entry->{title} };
        $mapped_title ||= $entry->{title};        

      	push @filtered_content, { location => $mapped_location
                               	 ,id => $entry->{id}
	                               ,title => $mapped_title
	                               ,start => $entry->{start}
	                               ,instructor => $entry->{description}
      	                        };
    }
    
    $native_outbound_content{schedule} = \@filtered_content;

    my $content = encode_json( \%native_outbound_content );
    print $cgi->header();
    print $content;

    my $now = DateTime->now();
    my $cache_content = encode_json( { %native_outbound_content
                        				      ,cacheTime => "$now"
                        				     } );

    my $fh = IO::File->new( ">$cache_path" ) || die "unable to create file at '$cache_path'!";
    print $fh $cache_content;
    $fh->close;

} else {

    die "COULD NOT FETCH!: " . $res->status_line . "\n";
}

