import json
import  pronouncing
import tweepy
import string
import credentials
import re
from time import time

start_time = time()
creds = credentials.get_credentials()
consumer_key = creds['consumer_key']
consumer_secret = creds['consumer_secret']
access_token = creds['access_token']
access_token_secret = creds['token_secret']

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

api = tweepy.API(auth)
time_limit_seconds = 300
limit_number_of_tweets_to_issue = 1
limit_number_of_tweets_to_read = 25000

class MyStreamListener(tweepy.StreamListener):
    number_of_tweets_issued = 0
    number_of_tweets_read = 0
    number_of_tweets_parsed = 0
    def on_status(self, status):
        # Apply a timeout
        current_time = time()
        if (current_time-start_time) > time_limit_seconds:
            print('Hit time limit')
            print('Number of tweets read:' + str(self.number_of_tweets_read))
            print('Number of tweets parsed:' + str(self.number_of_tweets_parsed))
            print('Time: ' + str(current_time-start_time))
            return False
        self.number_of_tweets_read += 1
        if self.number_of_tweets_read > limit_number_of_tweets_to_read:
            print('Hit number_of_tweets_read limit')
            print('Number of tweets read:' + str(self.number_of_tweets_read))
            print('Number of tweets parsed:' + str(self.number_of_tweets_parsed))
            print('Time: ' + str(current_time-start_time))
            return False
        if status.truncated:
            return True
        if hasattr(status, 'retweeted_status'):
            # Skip retweets
            # To do - parse the retweeted_status itself, track already tweeted statuses in a persistent cache (mongodb?)
            return True
        if status.in_reply_to_user_id and status.in_reply_to_user_id != status.user.id:
            # Skip replies to other users - kind of creepy to comment on others
            # Threads (replies to self) are fair game though
            return True
        if status.lang and status.lang != 'en':
            return True
        self.number_of_tweets_parsed += 1
        lines = [[] for i in range(3)]
        current_line = 0
        line_syllable_count = 0
        haiku_found = False
        haiku_disqualified = False
        for word in status.text.split():
            # Take out punctuation...
            word_stripped = word.translate(str.maketrans('', '', string.punctuation))
            # ... and non-ascii characters like emojis etc
            word_stripped.encode('ascii', 'ignore').decode('ascii')
            try:
                # This is the workhorse. Comes from pronouncing, which in turn comes from CMU's
                # Pronouncing dictionary. Gives a list, each element of which represents
                # the stress patterns of syllables in the word in standard North American pronunciation.
                # We don't need all this information, just the syllable count from the first entry.
                phones = pronouncing.phones_for_word(word_stripped)

                if(len(phones)):
                    # Does next word continue/complete te haiku?
                    # If so, add it in to the relevant line list
                    line_syllable_count += pronouncing.syllable_count(phones[0])
                    if haiku_found and line_syllable_count>0:
                        haiku_disqualified = True
                        break
                    target = 7 if current_line == 1 else 5
                    if line_syllable_count < target:
                        lines[current_line].append(word)
                    elif line_syllable_count == target:
                        lines[current_line].append(word)
                        current_line+=1
                        line_syllable_count = 0
                        if current_line == 3:
                            haiku_found = True
                    else:
                        haiku_disqualified = True
                        break
                else:
                    # exceptions to haiku disqualification should be: urls or words with no
                    # alphanumeric characters at start or end of tweet
                    if re.match('.*[a-zA-Z0-9]', word) and not re.match('^http', word):
                        haiku_disqualified = True
                        break
            except:
                haiku_disqualified = True
                break
        if haiku_found and not haiku_disqualified:
            # issue_tweet status, lines
            print(status.text)
            new_status = ''
            ct = 0
            for line in lines:
                ct+= 1
                for word in line:
                    if word == '&amp;':
                        word = '&'
                    new_status += word
                    new_status += ' '
                    print(word, end = ' ')
                if ct < 3:
                    new_status += '\\\n'
                    print('\\')
                else:
                    print('')
                    new_status += '\n'
            url = 'https://twitter.com/' + status.user.screen_name + '/status/' + status.id_str
            new_status += url
            api.update_status(new_status)
            self.number_of_tweets_issued += 1
            if self.number_of_tweets_issued >= limit_number_of_tweets_to_issue:
                # Exit after limit for tweets issued hit
                print('Got a haiku tweet!')
                print('Number of tweets read:' + str(self.number_of_tweets_read))
                print('Number of tweets parsed:' + str(self.number_of_tweets_parsed))
                current_time = time()
                print('Time: ' + str(current_time-start_time))
                return False

    def on_limit(self, track):
        """Called when a limitation notice arrives"""
        return False

def lambda_handler(event, context):

    myStreamListener = MyStreamListener()
    myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)

    myStream.sample()

    return {
        'message': 'Success!'
    }
