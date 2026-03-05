# Running Selenium on a VM

This README explains how to install Google Chrome, configure the environment, and run Selenium on a Linux VM.

## Install Python Dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv
```

## Install Google Chrome
- Add Google Chrome Signing Key
```bash
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | \
sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
```

- Verify the Key Exists
```bash
ls /usr/share/keyrings/google-chrome.gpg
```
```bash
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] \
http://dl.google.com/linux/chrome/deb/ stable main" | \
sudo tee /etc/apt/sources.list.d/google-chrome.list
```

- Install Google Chrome
```bash
sudo apt install -y google-chrome-stable
```

## Enable UI via VNC
- Install Desktop Environment and VNC Server
```bash
sudo apt update
sudo apt install -y \
  xfce4 xfce4-goodies \
  tightvncserver
```

- Start the VNC Server
```bash
vncserver
```
You will be prompted to set a password. This creates display :1 (usually port 5901).

- Connect from Local Machine
Create SSH Tunnel and Open VNC Viewer
```bash
ssh -N -L 5901:localhost:5901 -i qhung-ssh-key.pem qhung@172.188.81.139
vncviewer localhost:5901
```

The purpose is to sign-in manually via GUI to establish persistent chrome user profile on VM disk. 

## Run Chrome with a Specific Profile
```bash
cd ~/src
google-chrome --user-data-dir=./google-chrome --profile-directory=Profile_Twitter
```

## Copy Source Code to the VM
Copy Twitter Scraping Scripts
```bash
scp -i qhung-ssh-key.pem -r src/scraping/twitter/* \
  qhung@172.188.81.139:~/src/scraping/twitter/
```

Copy Entire Source Directory
```bash
scp -i qhung-ssh-key.pem -r src/* \
  qhung@172.188.81.139:~/src/
```
Copy Job Runner Script
```bash
scp -i qhung-ssh-key.pem \
  src/run_twitter_scraper_job.sh \
  qhung@172.188.81.139:~/src/run_twitter_scraper_job.sh
```

## Run cron job in VM

```bash
crontab -e
```
Schedule job (cron expression)
```bash
15 7,19 * * * ~/src/run_twitter_scraper_job.sh
```