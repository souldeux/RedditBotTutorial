import praw
import requests
import webbrowser
import re
from datetime import datetime

"""
Match results are posted in a URL that looks like this:
	
http://devcat.nexon.com/duel/us/arena/view?arenaName_arena_g.XX.1

XX is an incrementing integer which indicates the "round number" for the arena
arenaName is one of three strings:
	rookie
	randomdraft
	pvp
	
Two other arena types (newbie and veteran) are ignored at the request of someone who
understands how this game works.

Because of the way the target website is designed, accessing a URL for a match that does
not exist (ex: XX = -1) will lead you to a 404 page in a browser - but the actual response
code is 200 (because they're redirecting you to a 404 page with a kitty cat on it, but
giving response 200 when it loads). Fortunately, each arena also has its own API endpoint:

http://devcat.nexon.com/api-g/duel/arena/arenaName_arena_g.XX.1?lang=en_US

Where all the same arguments apply. When successful, this returns a JSON response object
where "description" is keyed to a list of dictionaries. These are listed in descending
order of score, meaning the first dict in the list corresponds to the winner of the 
given round. From that dict, we want the value keyed to "sharedDeck" so that we can
craft a URL which will allow us to view the winner's deck:

http://devcat.nexon.com/duel/us/deck?XXXXXXX

Where XXXXXXX corresponds to the sharedDeck value. There is some junk text that must be 
trimmed from the actual value in the dict before this URL can be crafted.

If that original API call fails, it does so with an appropriate status of 404 - helpful

We ultimately want to take all of this info and jam it into a reddit post once every two 
days.
"""

def refresh_oauth_login():
	#fancy oAuth login since password auth is being deprecated
	r = praw.Reddit("Mabinogi Duel Reporter / 1.0a")
	r.set_oauth_app_info(client_id="XXXX",
						client_secret="XXXX",
						redirect_uri="http://127.0.0.1:65010/authorize_callback")
	
	"""
	The following two lines should be uncommented if the app should ever need to be
	re-granted permissions. Then, use access_information with the new key to get a new
	refresh token
	"""
	#url = r.get_authorize_url('uniqueKey', 'identity submit history', True)
	#webbrowser.open(url)
	#access_information = r.get_access_information("accessTokenFromURL")
	
	refresh_token = "XXXX"
	r.refresh_access_information(refresh_token)
	
	return r
	
def get_match_details(arena, number):
	#Given an arena name and a number, returns the JSON response to the appropriate API
	#endpoint
	
	url = "http://devcat.nexon.com/api-g/duel/arena/{}.{}.1?lang=en_US".format(arena, number)
	#recall that this may be a 404!
	return requests.get(url).json()
	

def format_match_details(match):
	#Takes a JSON dump of match results and returns a dictionary with values
	#needed to craft a reddit post
	#Note that this must be a valid match - not a 404 response from get_match_details
	
	arena_name = match['title']
	round_number = match['round']
	id = match['id']
	match_url = "http://devcat.nexon.com/duel/us/arena/view?{}".format(id)
	crafted_description = "{} Round {}".format(arena_name, round_number)
	
	#see comments at start of file for why we're accessing this index
	winningDeck = match['description'][0]['sharedDeck'][2:]
	deck_url = "http://devcat.nexon.com/duel/us/deck?{}".format(winningDeck)
	
	return {'description':crafted_description, 'match_url':match_url, 'deck_url':deck_url}
	

def format_reddit_post(matchlist):
	#Reddit markdown requires that links be formatted like this:
	#[anchor text](http://url.com)
	
	#When passed a list of matches, creates a tuple of title, body for a new post
	body = ""
	for match in matchlist:
		body += "\n* [{}]({}) - [Champion's Deck]({})\n\n ".format(match['description'], 
															match['match_url'],
															match['deck_url'])
	
	body += " \n-----------------\n "
	body += " \nRemember: decks are subject to change every two hours. Listed decks may not always correspond to the decks the top 10 started the Arena with.\n "
	body += " \n-----------------\n"
	body += "by u/souldeux - please PM or contact at [souldeux.com](http://souldeux.com/contact) to report problems or request features"
	
	title = datetime.now().date().strftime('%b %d %Y Arena TOP 10s')
	
	return (title, body)
	
	
	 
def initialize_counters(r):
	#As of December 11th, 2015 counters were Rookie:11, Draft:21, PVP:11
	#Try to parse the last post made by this bot and start counters from the ones used
	#in there. If there is no last post for some reason, initialize with these counters.
	
	#Requires an r object from refresh_oauth_login
	
	#we only need the first (most recent) object provided by the generator
	last_post = r.get_me().get_submitted().next().selftext
	
	#Text in square brackets is the anchor text for the links in the post. There 
	#should always be an entry for the three arenas we're tracking, plus some other junk
	bracket_captures = set(re.findall("\[([^]]+)\]",last_post))
	
	#Iterate through the set of strings and take advantage of consistent formatting to
	#extract round numbers. increment them by one to get to the "next" rounds
	for description in bracket_captures:
		if description.startswith('PVP'):
			pvp_round = int(description.split(' ')[3]) + 1
		elif description.startswith('Rookie'):
			rookie_round = int(description.split(' ')[3]) + 1
		elif description.startswith('Random Draft'):
			draft_round = int(description.split(' ')[4]) + 1
		else:
			continue
	
	#Return results in a dict. The keys are formatted like we will need for use in our
	#get_match_details function
	
	return {'pvp_arena_g':pvp_round, 
			'rookie_arena_g':rookie_round, 
			'randomdraft_arena_g':draft_round}
			

def fetch_matches(counters):
	#Try to fetch matches. Returns a matchlist ready for format_reddit_post if successful,
	#or None if the request fails
	
	#Requires counters in the format provided by initialize_counters

	matchlist = []
	for arena, number in counters.items():
		details = get_match_details(arena, number)
		try:
			status = details['status']
			#this only executes on a failed request
			return None
		except:
			matchdict = format_match_details(details)
			matchlist.append(matchdict)
		
	return matchlist
	

def submit_match_update(matchlist, r):
	#Given a matchlist and a logged
	#in reddit object, submits a new reddit post with all good stuff included
	
	post_tuple = format_reddit_post(matchlist)
	submission = r.submit('secondsoulenterprises', post_tuple[0], text=post_tuple[1])
	return submission



if __name__ == '__main__':
	
	r = refresh_oauth_login()
	counters = initialize_counters(r)
	matchlist = fetch_matches(counters)
	if matchlist is not None:
		try:
			print submit_match_update(matchlist, r)
		except Exception as e:
			print e
	else:
		print "Sorry, you have requested a match that does not yet exist."
