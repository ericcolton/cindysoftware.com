#!/usr/bin/perl

#
#  wod.cgi
#
#  by Eric Colton
#  All rights reserved
#

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
use XML::Simple;

use Const;
use GymConfig;

my $USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9B179 Safari/7534.48.3';

my %WOD_DOMAINS = map { $_ => $GymConfig::GYMS->{ $_ }->{wod_domain} } keys %$GymConfig::GYMS;

my $DEFAULT_CACHE_TIMEOUT_SECS = 2 * 60 * 60;  # 2 hours

my $cgi = CGI->new();

my $gym_id_raw = $cgi->param('gymId');

my $gym_id;
if ( defined $gym_id_raw and $gym_id_raw =~ m/^([A-Z\-\_]{1,20})/ ) {

    $gym_id = $1;

} else {

    die "no gymId specified";
}

my $domain = $WOD_DOMAINS{ $gym_id };
unless ( $domain ) {
    die "gymId '$gym_id' unsupported";
}

my $cache_dir = "${Const::HOMEDIR}/cachedContent/${gym_id}/wod";

my $raw_date = $cgi->param('date');

my ( $year, $month, $day, $applicable_date );
if ( $raw_date =~ m/^(20\d{2})(\d{2})(\d{2})/ ) {

    $year  = $1;
    $month = $2;
    $day   = $3;
    $applicable_date = "$year$month$day";  # clean version of cgi 'date' param

} else {

    die "bad 'date' specified";
}

my $cache_path = File::Spec->catfile( $cache_dir, $applicable_date );

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
$ua->agent( $USER_AGENT );

# to get a day's wod, we actually request the previous day
#my $prevday = DateTime->new( year  => $year
#	                	,month => $month
#			    			,day   => $day
#                           );
#$prevday->add( days => -1 );
#my $prevday_str = sprintf( "%04d/%02d/%02d", $prevday->year, $prevday->month, $prevday->day );

my $day = DateTime->new( year => $year
                            ,month => $month
                            ,day => $day
                           );
my $day_str = sprintf("%04d/%02d/%02d", $day->year, $day->month, $day->day );
my $day_yyyymmdd_str = sprintf("%02d%02d%02d", $day->year % 100, $day->month, $day->day );

my ( $wod, $by_date_wods );
if ( $gym_id eq 'CROSSFITNYC' ) {

        my %dows = ( 1 => 'monday'
                    ,2 => 'tuesday'
                    ,3 => 'wednesday'
                    ,4 => 'thursday'
                    ,5 => 'friday'
                    ,6 => 'saturday'
                    ,7 => 'sunday'
                   );
  
        my $dow = $dows{ $day->day_of_week() };

	my $url_base = "http://${domain}/${day_str}/${dow}-${day_yyyymmdd_str}-";

        $wod = '';
        foreach my $type ( 'Beginner', 'Experienced', 'Competition' ) {

            my $url = $url_base . lc($type);

   	    my $req = HTTP::Request->new(GET => $url);
	    my $res = $ua->request($req);
	    if ( $res->is_success ) {
                $wod .= "<hr>" if ( $wod );
		$wod .= "<big><b>$type:</big></b><br><br>" . parse_crossfitnyc($res->content);
	    } else {
	        die "COULD NOT FETCH WOD FOR $gym_id!: " . $res->status_line . "\n";
	    }
        }

} elsif ( $gym_id eq 'CFG' ) {

	$ua->parse_head(0);

	my $url = "http://${domain}";

	my $req = HTTP::Request->new(GET => $url);
	my $res = $ua->request($req);
	my $content = $res->decoded_content;

	if ( $res->is_success ) {
		$by_date_wods = parse_cfg($content);
	} else {
	    die "COULD NOT FETCH WOD FOR $gym_id!: " . $res->status_line . "\n";		
	}

} elsif ( $gym_id = 'CROSSFITLIC' ) {

	# for CrossFit LIC, go back a few days if wod not found on the same-day
	my $searchday = DateTime->new( year  => $year
    	                          ,month => $month
			                      ,day   => $day
                                 );

    my $search_str = sprintf("%s,\\s+%s\\s+%d,\\s+%d", $searchday->day_name, $searchday->month_name, $searchday->day, $searchday->year);
    my $url_suffix = sprintf("%s-%s-%d-%d", (lc $searchday->day_name), (lc $searchday->month_name), $searchday->day, $searchday->year);
	for my $offset ( 1, 0, 2 ) {

		my $tryday = DateTime->new( year  => $year
    	                           ,month => $month
			     	               ,day   => $day
                                  );

		$tryday->add( days => -1 * $offset );

		my $tryday_str = sprintf( "%04d/%02d/%02d", $tryday->year, $tryday->month, $tryday->day );
		my $url = "http://${domain}/${tryday_str}/${url_suffix}";

		my $req = HTTP::Request->new(GET => $url);
		my $res = $ua->request($req);
		if ( $res->is_success ) {
			$wod = parse_crossfitlic($res->content, $search_str);
			last if ( $wod );
		}
	}

} else {

	die "url for gym $gym_id not configured!";
}

if ( $wod ) {

	$by_date_wods = { $applicable_date => $wod };
}

my $found_result_for_today;
if ( $by_date_wods and %$by_date_wods ) {

	my $now = DateTime->now();

	foreach my $date ( keys %$by_date_wods ) {

		my $wod_for_date = $by_date_wods->{$date};

		my %native_content = ( date    => $date
	          			      ,version => 0.1
			                  ,wodDesc => $wod_for_date
	        	             );

		my $cache_content = encode_json( { %native_content
	                				      ,cacheTime => "$now"
		               				     });

		my $path = File::Spec->catfile( $cache_dir, $date );
		my $fh = IO::File->new( ">$path" ) || die "unable to create file at '$path'!";
		print $fh $cache_content;
		$fh->close;

		if ( $date eq $applicable_date ) {	
			$found_result_for_today = 1;

			my $content = encode_json( \%native_content );
		    print $cgi->header();
			print $content;
		}
	}

	unless ( $found_result_for_today ) {

		my %native_content = ( date    => $applicable_date
	          			      ,version => 0.1
			                  ,wodDesc => ""
	        	             );

		my $cache_content = encode_json( { %native_content
	                				      ,cacheTime => "$now"
		               				     });

		my $path = File::Spec->catfile( $cache_dir, $applicable_date );
		my $fh = IO::File->new( ">$path" ) || die "unable to create file at '$path'!";
		print $fh $cache_content;
		$fh->close;

		my $content = encode_json( \%native_content );
		print $cgi->header();
	print $content;
	}

} else {

	die "No wod parsed for '$gym_id'!";
}

sub parse_crossfitnyc {
    my ( $raw ) = @_;

    $raw =~ s/\n//g;

    $raw =~ m#<section class\="entry\-content clearfix" itemprop\="articleBody">\s*(.+?)</section>#;
    my $section = $1;

    $section =~ s|<p><em>Here\&\#8217\;s (.*?)</p>||;

    return $section;
}


=pod 

sub parse_crossfitnyc {
	my ( $raw ) = @_;

    my $content = XML::Simple::XMLin( $raw, force_array => 1 );
    
    my $items = $content->{channel}->[0]->{item};

   	foreach my $item ( @$items ) {

		if ( $item->{title}->[0] =~ m/^\w{3,6}day \d{6,8}$/ ) {

		    my $wod = $item->{'content:encoded'}->[0];

		    # chop off video/image content
		    $wod =~ s/<img.*//s;
		    $wod =~ s/<script.*//s;

		  	#chop off trailing link
	 		$wod =~ s/<a href.*?$//;

	 		return $wod;
	 	}
	}
}

=cut 

sub parse_crossfitlic {
	my ( $raw, $search ) = @_;

		if ( $raw =~ m/$search(.|\n)*?<div class="entry">(.|\n)*?(<p>(.|\n)*)/ ) {

		my $parsed = $3;
		$parsed =~ s#</div>(.|\n)*##;

		# get rid of images
		$parsed =~ s#<img(.|\n)+?/>##g;

		return $parsed;
	}
}

=pod

sub parse_cfg {
	my ( $raw ) = @_;

	my $regex_date = qq[<h3 class=\"field\-content\">[A-Z]+\\s+(\\d+)\\.(\\d+)</h3>];

	my $now = DateTime->now;
	my $year = $now->year;

	my %by_date_wods;
	while ( $raw =~ s|$regex_date|| ) {

		my ($month, $dom) = ( sprintf("%02d", $1), sprintf("%02d", $2) );

		my $regex_wod = qq[(<p>.*?</p>)];

		my $wod;
		if ( $raw =~ s|$regex_wod|| ) {
		    $wod = $1;
		}

		$by_date_wods{"$year$month$dom"} = $wod;
	}

	return \%by_date_wods;
}

=cut

sub parse_cfg {
	my ( $raw ) = @_;

	my $now = DateTime->now;
	my $year = $now->year;

	my %by_date_wods;

	print "SEE: $raw\n";
	$raw =~ s/\n/<br>/g;
	while ( $raw =~ s|alt="\w+\s+(\d+)\.(\d+)(.*?)"/>|| ) {

		my ($month, $dom, $wod) = ( sprintf("%02d", $1), sprintf("%02d", $2), $3 );
		$by_date_wods{"$year$month$dom"} = $wod;
	}

	return \%by_date_wods;
}






