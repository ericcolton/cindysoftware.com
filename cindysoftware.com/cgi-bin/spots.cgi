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

use Const;
use GymConfig;

my %SUBDOMAINS = map { $_ => $GymConfig::GYMS->{ $_ }->{subdomain} } keys %$GymConfig::GYMS;

my $USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9B179 Safari/7534.48.3';
my $DEFAULT_CACHE_TIMEOUT_SECS = 3 * 60;  # 3 minutes
my $SHORT_CACHE_TIMEOUT_SECS = 3;  # 3 seconds

my $cgi = CGI->new();

my $date_param = $cgi->param('date');
die "no 'date' argument specified" unless ( $date_param );

my $gym_id_raw = $cgi->param('gymId');

my $gym_id;
if ( defined $gym_id_raw and $gym_id_raw =~ m/^([A-Z\-\_]{1,20})/ ) {
    $gym_id = $1;
} else {
    die "no gymId specified";
}

my $subdomain = $SUBDOMAINS{ $gym_id };
unless ( $subdomain ) {
    die "gymId '$gym_id' unsupported";
}

my $urlbase = "https://${subdomain}.sites.zenplanner.com/calendar.cfm?calendarType=&date=";

my $cache_dir = "$Const::HOMEDIR/cachedContent/${gym_id}/spots";


my ( $yyyymmdd ) = $date_param =~ m/^(20\d{6})/;

my ( $no_cache ) = $cgi->param('noCache');

die "invalid date string specified" unless ( $yyyymmdd );

my $cache_path = File::Spec->catfile( $cache_dir, $yyyymmdd );

if ( -e $cache_path ) { 

    my $modtime_secs = (-M $cache_path) * 24 * 60 * 60; # seconds ago file was modified
    
    if ( $modtime_secs < $SHORT_CACHE_TIMEOUT_SECS
	 or ( !$no_cache and $modtime_secs < $DEFAULT_CACHE_TIMEOUT_SECS )
       ) {
		my $content = File::Slurp::read_file( $cache_path );
        print $cgi->header();
        print $content;
		exit(0);
    }
}

my $ua = LWP::UserAgent->new();
$ua->agent( $USER_AGENT );

my ( $yyyy, $mm, $dd ) = $yyyymmdd =~ m/(20\d{2})(\d{2})(\d{2})/ or die "unexpected format of 'date'!: $yyyymmdd";

my $formatted_date = "$yyyy-$mm-$dd";

my $req = HTTP::Request->new(GET => "${urlbase}$formatted_date");

my $res = $ua->request($req);

if ($res->is_success) {

    my $content = $res->content;

    my ( $subcontent ) = $content =~ m|<table class="table calendar">(.*?)</table>|s;
    if ( $subcontent ) {

		my $regex = qq[<tr style=".*?" onclick="checkLoggedId\\('appointment\\.cfm\\?appointmentId\\=([\\w\\-]*?)'\\);">
<td.*?>.*?</td>
<td.*?>.*?</td>
<td.*?>
<span class=".*?">(\\w*?)</span>
</td>
</tr>];

	my @entries;
	while ( $subcontent =~ s/$regex//s ) {

	    my ( $appointmentId, $spotsAvail ) = ( $1, $2 );

	    # appointmentId => spotsRemaining (or 'FULL')
	    my %entry = ( workoutId => $appointmentId );
	    if ( $2 eq 'FULL' ) {
		$entry{isFull} = 1;
	    } else {
		$entry{isFull} = 0;
		$entry{spotsAvail} = $spotsAvail;
	    }
	    push @entries, \%entry;
	}

	my %native_content = ( date => $yyyymmdd
			              ,version => 0.1
			              ,appointmentSpots => \@entries
	                     );

    my $content = encode_json( \%native_content );
    print $cgi->header();
	print $content;

	my $now = DateTime->now();
    my $cache_content = encode_json( { %native_content
				                      ,cacheTime => "$now"
					                 } );

	my $fh = IO::File->new( ">$cache_path" ) || die "unable to create file at '$cache_path'!";
	print $fh $cache_content;
	$fh->close;
    }

} else {
	
    die "COULD NOT FETCH!: " . $res->status_line . "\n";
}
