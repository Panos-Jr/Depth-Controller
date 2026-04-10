# <img src="https://github.com/Panos-Jr/Depth-Controller/blob/main/anchor.png" style="height:2.1rem;vertical-align:middle;margin-right:.6rem;"> Depth Controller
Self-hosted flask server that allows you to configure your dedicated server for <b>Depth</b>. 
Details about the game can be found <a href=https://store.steampowered.com/app/274940/Depth/>here</a>.
<br>
The web client features `map rotation` which can be toggled, allowing you to automatically move to the next map (on the list) after restarting

## Accessing the web client
The app itself will be running in the background and can be found on your tray, as shown.
Accessing the web client is simple, just right-click and press <b>Open Controller</b> <br>
<img width="234" height="114" alt="image" src="https://github.com/user-attachments/assets/9f6d2a6d-c894-4dd7-828e-16002e33a494" />

or you can access it via <a href="http://localhost:5000/">http://localhost:5000/</a>, the web client is using port <b>5000</b> which will need to be port forwarded on your router, and make sure your IP is static.

## UI
<img width="1920" height="945" alt="image" src="https://github.com/user-attachments/assets/608a2572-8f68-417a-85a2-fc768315fc53" />

If you didn't know already, the developers of Depth haven't included rounds within the dedicated servers, so you'll need to restart the server for each game you finish (and your game, which means you'll also have to reconnect each time, including your friends). This is what I had in mind when building the UI for the web client, hence why it's simply `restart server`. To make the restart as seamless as possible for you and your friends, you can combine the <b>Depth Controller</b>, with my <a href=https://github.com/Panos-Jr/Depth-Launcher><b>Depth Launcher</b></a>. More info on how to get started with that below.

Quick note: If you are planning to do this on a LAN with your friends, you don't need to worry about using Caddy, and your friends can just use your local IP on the launcher. Like so, {private IP}:5000

<img width="362" height="332" alt="image" src="https://github.com/user-attachments/assets/82207bbe-44b6-44ae-b152-bf6ae80decf9" />



## Caddy
To get the web client accessible outside your home network, you'll need to setup a reverse proxy, I'll be showing you how to get started with Caddy, though any alternatives like nginx should suffice.

Download Caddy from <a href="https://caddyserver.com/">here</a>, and ideally install it on the root of your C:\ drive. `C:\caddy` would be a good place. 

To get setup, you'll need a Caddyfile, which is a config file Caddy will use. This is what I've used in my case, just replace `example.com` with your actual domain. If you need a domain, you can easily obtain a free one from <a href="https://www.noip.com/">No-IP</a>.
```
example.com {
    reverse_proxy localhost:5000
}
```

Your `caddy` folder should like this,

<img width="673" height="103" alt="image" src="https://github.com/user-attachments/assets/67263d47-971c-4cf8-9505-e842169e7799" />

Once you've got <b>Depth Controller</b> open, you can run the command `caddy run --config Caddyfile`
and the web client should be accessible using your domain.

Now take that domain, and apply it to <a href=https://github.com/Panos-Jr/Depth-Launcher><b>Depth Launcher</b></a>, which will check when the server restarts and will restart your game for you. Or start it if it isn't already, and connect to the dedicated server. (Keep <b>Depth Launcher</b> in your game files, inside the Depth folder)

## Issues

If you do install <b>Depth Controller</b> to the Program Files directory make sure you run it as <b>administrator</b>.  Doesn't function correctly if ran normally. Should be fine anywhere else though.


## Credits
<a href="https://www.flaticon.com/free-icon/anchor_9478715?term=anchor&page=1&position=89&origin=tag&related_id=9478715" title="anchor icons">Anchor icon created by Mayor Icons - Flaticon</a>





