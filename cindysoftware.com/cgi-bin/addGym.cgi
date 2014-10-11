#!/usr/bin/perl

use strict;
use CGI;
use JSON;
use LWP::UserAgent;
use File::Spec;
use File::Slurp;
use IO::File;
use DateTime;
use Data::Dumper;
use XML::Simple;
use HTML::Entities;

my $cgi = CGI->new();

my $EMAIL_ADDR = 'info@cindysoftware.com';

print $cgi->header;

my $error;
my $website = $cgi->param('gym_website');
$website = substr( $website, 0, 50 );
if ( $website and $website !~ m/^(\S+)\.(\S+)$/ ) {
	$error = "'$website' is not a valid website";
}

my $state   = $cgi->param('gym_state');
$state = substr( $state, 0, 50 );
unless ( $state ) {
	$error = "must select a state";
}

my $name  = $cgi->param('gym_name');
$name = substr( $name, 0, 200 );
unless ( $name ) {
	$error = "must specify a gym name or other identifier";
}

my $email   = $cgi->param('user_email');
$email = substr( $email, 0, 50 );
if ( $email and $email !~ m/^(\S+)\@(\S+)\.(\S+)$/ ) {
	$error = "'$email' does not appear to be a valid email address";
}

my ( $msg, $title );
if ( $error ) {

	$title = "Please fix this submission error";
	$msg = qq[<font color="RED">$error</font>];

} else {

	$title = "Thank you!";
	$msg = "Your request has been recorded! Thank you for your interest.";
	send_mail( "new gym request: $name", qq[
NAME: $name
WEBSITE: $website
STATE: $state
EMAIL: $email
		]);
}


print qq[
<!DOCTYPE html> 
<html>
<head>
	<title>Add a Gym</title>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	
	<link rel="stylesheet" href="http://code.jquery.com/mobile/1.4.0/jquery.mobile-1.4.0.min.css" />
	
	<script src="http://code.jquery.com/jquery-1.11.0.min.js"></script>
	<script src="http://code.jquery.com/mobile/1.4.0/jquery.mobile-1.4.0.min.js"></script>
	<script>
	\$( function() {

		var backButton= \$("#backButton");
		backButton.on("click", function() { 
		jQuery.mobile.navigate("../addGymActual.html");
		
		});
	});

	</script>
</head>

<body>
	<div data-role="page" id="requestPage">
			<div data-role="header">$title</div>
			<div role="main" class="ui-content">$msg
			<br><br>
			<button id="backButton">Back</button>
			</div> 

			<div data-role="footer">

			</div>
	</div>
	<div data-role="page" id="completedPage">
			<div data-role="header">part 2 start...</div>
			<div role="main" class="ui-content">...part 2 content...<a href="#foo">link to #foo</a>
			<a href="http://cnn.com" data-prefetch="true">and this gets CNN!</a>
			</div>
			<div data-role="footer">...part 2 end</div>
	</div>
</body>
</html>
];

sub send_mail {
    my ( $subject, $body ) = @_;

    my $mailprog = '/usr/sbin/sendmail';
    my $from_address = $EMAIL_ADDR;
    my $to_address = $EMAIL_ADDR;
    open (MAIL, "|$mailprog -t $to_address") || die "Can't open $mailprog!\n";
    print MAIL "To: $to_address\n";
    print MAIL "From: $from_address\n";
    print MAIL "Subject: $subject\n";
    print MAIL "$body\n";
    close (MAIL);
}
