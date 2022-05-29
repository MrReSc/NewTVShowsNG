from fcntl import DN_DELETE
import re
import unicodedata
import requests
import feedparser
import time
import pickle
import os.path
from urllib.parse import urlparse
from datetime import datetime as dt

# Um das Skript zu debugen, kann die Umgebungsvariable NEW_TV_DEBUG auf True gesetzt werden
try:
    DEBUG = os.environ["NEW_TV_DEBUG"]
except:
    DEBUG = False

JELLY_API_KEY = os.environ["JELLY_API_KEY"]
JELLY_USER_ID = os.environ["JELLY_USER_ID"]
JELLY_IP = os.environ["JELLY_IP"]
RSS_URLS = str(os.environ['RSS_URLS']).split(',')

DATA = 'data/data.pickle' if DEBUG else '/data/data.pickle'
OUTPUT = 'out/index.html' if DEBUG else '/out/index.html'
MAX_COUNT = int(os.environ["MAX_COUNT"])

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

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
        return time.strftime(DATE_FORMAT, date_parsed)
    except:
        return date  

def string_found(search, string):
    index = string.find(search)
    # Feed Titel beginnt mit dem Show Titel und hat am Ende ein Space
    if index == 0 and string[index + len(search)] == " ":
        return True
    else:
        return False    

def checkForDuplicate(new):   
    for show in showsRSS:
        # Überprüfen ob Link schon vorhanden ist
        if new["Link"] == show["Link"]:
            # Wenn Link schon vorhanden ist, dann überprüfen ob er neuer ist
            nd = dt.strptime(new["Published"], DATE_FORMAT)
            sd = dt.strptime(show["Published"], DATE_FORMAT)
            if nd >= sd:
                # Wenn er neuer oder gleich ist dann kann der alte gelöscht werden
                showsRSS.remove(show)    

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
                            if new in showsRSS:
                                showsRSS.append(new)
                                checkForDuplicate(new)
        except KeyError:
            pass

##############################################################################
# Daten speichern
##############################################################################
# Wenn die Liste zu lang wird, wird solange das älteste Element entfernt bis die Liste nicht mehr zu Gross ist
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
BG_COLOR   = "#1e1e1e"
FG_COLOR   = "#ffffff"
BORDER     = "#3f3f3f"
HEADER     = "#333333"
LINK       = "#007acc"
V_LINK     = "#c58af9"
SEASON     = "#242424"
SEASON_NEW = "#b73db7"

strStyle = '''<style> 
table, td { border: 1px solid ''' + BORDER + '''; border-collapse: collapse; } 
th { border: 1px solid ''' + BORDER + '''; border-collapse: collapse; background-color : '''+ HEADER +''';} 
input[type="text"] { background-color : '''+ BG_COLOR +'''; color: ''' + FG_COLOR + '''; margin-bottom: 25px; padding: 5px;}
body { font-family: 'Courier New', monospace; font-size: 120%;}
</style>'''
strTitle = '''
<title>NewTVshowNG</title>
<link rel="icon" type="image/x-icon" href="../favicon.ico">
'''
strBodyStyle = 'bgcolor="' + BG_COLOR + '" text="' + FG_COLOR + '" link="' + LINK + '" vlink="' + V_LINK + '" alink="' + LINK + '"'
strInput = '<input type="text" id="myInput" onkeyup="myFunction()" placeholder="nach Qualitaet suchen...">'
strHeader = '<table id="myTable"><tr><th>Titel</th><th>S</th><th>E</th><th>SJ</th><th>EJ</th><th>Link</th><th>Datum</th><th>Qualitaet</th></tr>'
strTable = "<!DOCTYPE html><html><head>" + strStyle + strTitle +  '</head><body ' + strBodyStyle + '>' + strInput + strHeader
 
for show in showsRSS:
    domain = urlparse(show["Link"]).netloc
    if show["Season"] <= show["SeasonJellyfin"]:
       SEASON_NEW = BG_COLOR 
    else:
        if show["EpisodeJellyfin"] <= show["Episode"]:
            SEASON_NEW = BG_COLOR

    strRW = '<tr><td>' + show["Name"][:100] + '</td><td width="50" bgcolor="' + SEASON +' " style="text-align:center">'\
                       + str(show["Season"] or '') + '</td><td width="50" bgcolor="' + SEASON + '" style="text-align:center">'\
                       + str(show["Episode"] or '') + '</td><td width="50" bgcolor="' + SEASON_NEW + '" style="text-align:center">'\
                       + str(show["SeasonJellyfin"] or '') + '</td><td width="50" bgcolor="' + SEASON_NEW + '" style="text-align:center">'\
                       + str(show["EpisodeJellyfin"] or '') + '</td><td>'\
                       + '<a href="' + show["Link"] + '" target="_blank" title="' + show["Link"] + '">'+ domain +'</a></td><td>'\
                       + str(show["Published"] or '') + '</td><td style="text-align:center">'\
                       + str(show["Quality"] or '') + '</td></tr>' 

    strTable = strTable + strRW

js = '''
<script>
function myFunction() {
  var input, filter, table, tr, td, i, txtValue;
  input = document.getElementById("myInput");
  filter = input.value.toUpperCase();
  table = document.getElementById("myTable");
  tr = table.getElementsByTagName("tr");
  for (i = 0; i < tr.length; i++) {
    td = tr[i].getElementsByTagName("td")[7];
    if (td) {
      txtValue = td.textContent || td.innerText;
      if (txtValue.toUpperCase().indexOf(filter) > -1) {
        tr[i].style.display = "";
      } else {
        tr[i].style.display = "none";
      }
    }       
  }
}
</script>
'''

strTable = strTable + "</table>" + js + "</body></html>"
 
hs = open(OUTPUT, 'w')
hs.write(strTable)