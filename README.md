# NewTVShowsNG

```
version: '2.1'

services:
  new_tv_shows:
    image: ghcr.io/mrresc/newtvshowsng:master
    container_name: NewTvShowsNG
    restart: always
    build: .
    volumes:
      - ./out:/out:z
      - ./data:/data:z
    environment:
      - JELLY_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      - JELLY_USER_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      - JELLY_IP=http://192.168.0.2:8096
      - MAX_COUNT=300
      - TZ=Europe/Zurich
      - RSS_URLS=www.url.xyv/rss,www.url.gg/feed

  web:
    image: nginx:latest
    container_name: NewTvShowsNGweb
    volumes:
      - ./out:/usr/share/nginx/html
    ports:
      - "28800:80"   
```