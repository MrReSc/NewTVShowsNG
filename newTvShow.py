import re
import unicodedata
import requests
import feedparser
import time
import pickle
import os.path
from urllib.parse import urlparse

JELLY_API_KEY = os.environ["JELLY_API_KEY"]
JELLY_USER_ID = os.environ["JELLY_USER_ID"]
JELLY_IP = os.environ["JELLY_IP"]
RSS_URLS = str(os.environ['RSS_URLS']).split(',')

DATA = '/data/data.pickle'
OUTPUT = '/out/index.html'
MAX_COUNT = int(os.environ["MAX_COUNT"])

showsJellyfin = []
showsRSS = []

def cleanName(name):   
    name = re.sub(r'\(.*\)', '', name)                                                          # löscht alles in Klammern und Klammern (Blafoo2017)
    name = name.replace("-", " ").replace("–", " ")                                             # Bindestriche durch Leerzeichen ersetzten
    name = name.replace("ä", "ae").replace("ü", "ue").replace("ö", "oe")                        # äöü ersetzten
    name = str(unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode("utf-8"))    # Akzente entfernen
    name = re.sub(r'[^A-Za-z0-9 ]+', '', name)                                                  # löscht alles was nicht Buchstabe, Leerzeichen oder Zahl ist  
    name = re.sub(r' +', ' ', name)                                                             # löscht unnötige Leerzeichen
    name = name.lower()                                                                         # alles lower case
    return name

def getEpisode(name):
    match = re.search(r"(?:e|episode|\n)(\d{2})", name, re.I)
    return match.group(1) if match else ""    


def getSeason(name):
    match = re.search(r"(?:s|season)(\d{2})", name, re.I)
    return match.group(1) if match else ""     


def getQuality(name):
    match = re.search(r"(\d{3,4}p)", name, re.I)
    return match.group(1) if match else ""  


def getPubDate(date_parsed, date):
    try:
        return time.strftime('%Y-%m-%d %H:%M:%S', date_parsed)
    except:
        return date  

def string_found(search, string):
    index = string.find(search)
    # Feed Titel beginnt mit dem Show Titel und hat am Ende ein Space
    if index == 0 and string[index + len(search)] == " ":
        return True
    else:
        return False    


##############################################################################
# Persitente Daten laden
##############################################################################
if os.path.isfile(DATA):
    infile = open(DATA,'rb')
    showsRSS = pickle.load(infile)
    infile.close() 
else:
    file = open(DATA, 'w+')

##############################################################################
# JELLYFIN
##############################################################################
# Vorhandene Serien über Jellyfin API abrufen und aufbereiten
respond = requests.get(JELLY_IP + '/emby/Users/' + JELLY_USER_ID + '/Items?Recursive=true&IncludeItemTypes=Series&api_key=' + JELLY_API_KEY).json()
for show in respond['Items']:
    showsJellyfin.append({"Name" : cleanName(show['Name']), "Id" : show['Id'], "LastEpisode" : "", "LastSeason" : ""})

# Letzte vorhandene Staffel und Episode über Jellyfin API abrufen
for show in showsJellyfin:
    # Staffel abrufen
    respond = requests.get(JELLY_IP + '/Shows/' + show["Id"] + '/Seasons?api_key=' + JELLY_API_KEY).json()
    if respond['TotalRecordCount'] > 0:
        # Id der letzten vorhandenen Staffel
        seasonId = respond['Items'][-1]["Id"]
        # Episode abrufen
        respond = requests.get(JELLY_IP + '/Shows/' + show["Id"] + '/Episodes?seasonId=' + seasonId + "&api_key=" + JELLY_API_KEY).json()
        s = respond['Items'][-1]["ParentIndexNumber"]
        e = respond['Items'][-1]["IndexNumber"]
        show["LastEpisode"] = f"{e:02d}"
        show["LastSeason"] = f"{s:02d}"

##############################################################################
# RSS auswerten
##############################################################################
feeds = [feedparser.parse(url)['entries'] for url in RSS_URLS]

for feed in feeds:
    for item in feed:
        try:
            name = cleanName(str(item["title"]).replace(".", " "))
            episode = getEpisode(name)
            season = getSeason(name)
            quality = getQuality(name)
            pubDate = getPubDate(item["published_parsed"], item["published"])
            # Wenn season = "" dann wird es ein Film sein
            if season:
                # Überprüfen ob etwas dabei ist das auf dem Server vorhanden ist
                for show in showsJellyfin:
                    seasonJellyfin = show["LastSeason"]
                    episodeJellyfin = show["LastEpisode"]
                    if string_found(show["Name"], name):
                        # Wenn keine Staffel Information vorhanden ist auf dem Server oder
                        # wenn gleiche Staffel vorhanden ist und Episode neuer oder
                        # wenn Staffel auf Server älter ist
                        if (not seasonJellyfin) or (seasonJellyfin == season and episode > episodeJellyfin) or (seasonJellyfin < season or (season and not episode)):
                            new = {"Name" : item["title"], "Link" : item["link"], 
                            "Episode" : episode, "Season" : season,
                            "EpisodeJellyfin" : episodeJellyfin, "SeasonJellyfin" : seasonJellyfin,
                            "Quality" : quality, "Published" : pubDate}
                            # Wenn Daten noch nicht vorhadnen dann hinzufügen
                            if new not in showsRSS:
                                showsRSS.append(new)
        except KeyError:
            pass

##############################################################################
# Daten speichern
##############################################################################
# Wenn die Liste zu lamg wird, wird solange das älteste Element entfernt bis die Liste nicht mehr zu Gross ist
while len(showsRSS) > MAX_COUNT:
    showsRSS.pop(0)

try:
    outfile = open(DATA,'wb')
    pickle.dump(showsRSS, outfile)
    outfile.close()
except:
    pass

##############################################################################
# Daten in HTML umwandeln
##############################################################################
# Sortieren
showsRSS = sorted(showsRSS, key=lambda d: d['Published'], reverse=True) 

# HTML generieren
strStyle = '<style> table, th, td { border: 1px solid white; border-collapse: collapse; }</style>'
strBodyStyle = 'bgcolor="#1e1e1e" text="#ffffff" link="#5f78a1" vlink="#c58af9" alink="#5f78a1"'
strTable = "<html><head>" + strStyle + '</head><body ' + strBodyStyle + '><table><tr><th>Titel</th><th>S</th><th>E</th><th>SJ</th><th>EJ</th><th>Link</th><th>Datum</th><th>Qualität</th></tr>'
 
for show in showsRSS:
    domain = urlparse(show["Link"]).netloc
    strRW = '<tr><td>' + show["Name"] + '</td><td width="50" bgcolor="#682d68" style="text-align:center">'\
                       + str(show["Season"] or '') + '</td><td width="50" bgcolor="#682d68" style="text-align:center">'\
                       + str(show["Episode"] or '') + '</td><td width="50" style="text-align:center">'\
                       + str(show["SeasonJellyfin"] or '') + '</td><td width="50" style="text-align:center">'\
                       + str(show["EpisodeJellyfin"] or '') + '</td><td>'\
                       + '<a href="' + show["Link"] + '" target="_blank">'+ domain +'</a></td><td>'\
                       + str(show["Published"] or '') + '</td><td style="text-align:center">'\
                       + str(show["Quality"] or '') + '</td></tr>' 

    strTable = strTable + strRW
 
strTable = strTable+"</table></body></html>"
 
hs = open(OUTPUT, 'w')
hs.write(strTable)