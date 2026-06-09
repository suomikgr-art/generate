<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff7b00,100:ff0000&height=200&section=header&text=TSun%20FF%20Generator&fontSize=40&fontColor=ffffff&animation=fadeIn&fontAlignY=35"/>
</p>

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?size=22&duration=4000&color=FF6B00&center=true&vCenter=true&width=600&lines=High-Speed+Free+Fire+Guest+Generator;Multi-threaded+%7C+Rare+Finder+%7C+JWT+Extractor;Built+for+Power+Users+%F0%9F%94%A5"/>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/TSun-FreeFire/TSun-FF-Guest-Generator?style=for-the-badge" />
  <img src="https://img.shields.io/github/forks/TSun-FreeFire/TSun-FF-Guest-Generator?style=for-the-badge" />
  <img src="https://img.shields.io/github/issues/TSun-FreeFire/TSun-FF-Guest-Generator?style=for-the-badge" />
  <img src="https://img.shields.io/github/license/TSun-FreeFire/TSun-FF-Guest-Generator?style=for-the-badge" />
</p>

---

> 💬 *“Generating power, detecting rair accounts and couple accounts — unlimited accounts”*

<p align="center">
  <img src="https://media.giphy.com/media/ZVik7pBtu9dNS/giphy.gif" width="500"/>
</p>

---

<div align="center">

# ✨ Features

</div>

🚀 **Speed & Performance**
* Multi-threaded generation engine
* Optimized for high throughput
* Single or bulk proxy rotation from `proxies.txt`
* Alive proxy checker that keeps working proxies active and moves dead ones offline

🌍 **Global Coverage**
* Supports multiple regions: `PK`, `IND`, `ID`, `ME`, `VN`, `TH`, `BD`, `TW`, `CIS`, `SG`, `SAC`

👻 **GHOST Mode**

* Alternate endpoint generation system for unique accounts

🔐 **JWT Token Extraction**

* Auto-captures and stores authentication tokens

💎 **Rare Account Detection**

* Intelligent scoring system based on ID patterns

💑 **Couples Matching**

* Detects sequential & mirrored account pairs across threads

📁 **Clean Data Storage**

* Structured JSON outputs
* Thread-safe file operations

---
<div align="center">

## 🧠 **Tech Stack**
</div>

<p align="center">

<img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python"/>
<img src="https://img.shields.io/badge/Threading-Enabled-orange?style=for-the-badge"/>
<img src="https://img.shields.io/badge/JSON-Storage-lightgrey?style=for-the-badge"/>
<img src="https://img.shields.io/badge/AES-Encryption-green?style=for-the-badge"/>
<img src="https://img.shields.io/badge/CLI-Interface-black?style=for-the-badge"/>

</p>

---

## ⚙️ **Installation**

### Clone the repo
    git clone https://github.com/TSun-FreeFire/TSun-FF-Guest-Generator.git
### Enter directory
    cd TSun-FF-Guest-Generator
### Install dependencies
    pip install -r requirements.txt
### Run the app
    python app.py

### Network mode (Recommended)
During generation you can choose one of two network modes:

* `Original network (DIRECT)` - uses your real internet connection and ignores `proxies.txt`.
* `Proxy rotation` - loads valid entries from `proxies.txt` and rotates requests through them.

### Optional proxy rotation
Create a `proxies.txt` file in the project root. One proxy per line. Comma-separated lines and trailing commas are also accepted:

```txt
ip:port
ip:port,
ip:port:username:password
username:password:ip:port
ip:port@username:password
username:password@ip:port
http://username:password@ip:port
```

The generator reloads `proxies.txt` at generation start and rotates the full account pipeline through the list. Use menu option `3` to check alive proxies; alive proxies stay in `proxies.txt`, while dead, timed-out, invalid, or auth-failed entries are moved to `offline_proxies.txt`.

---
<div align="center">

## 🎛️ Menu Overview
</div>

| Option | Description         |
| ------ | ------------------- |
| `1`    | Generate Accounts   |
| `2`    | View Accounts       |
| `3`    | Check Alive Proxies |
| `4`    | About               |
| `0`    | Exit                |

---
<div align="center">

## ⚡ **Generation Flow**
</div>


1. Select region or **GHOST Mode**
2. Enter number of accounts
3. Set username prefix
4. Set password prefix
5. Choose rarity threshold
6. Set thread count (💡 recomended: 4 Or 10)
7. Choose network mode: original network or proxy rotation

---
<div align="center">

## 📂 **Output Structure**
</div>

```
TSun-Studio/
├── ACCOUNTS/
├── TOKENS-JWT/
├── RARE ACCOUNTS/
├── COUPLES ACCOUNTS/
└── GHOST/
```
<div align="center">

✔ Clean
✔ Organized
✔ Easy to parse
</div>

---
<div align="center">

## 💎 **Rare Account System**
</div>

| Pattern                           | Score |
| --------------------------------- | ----- |
| 🔢 Uniform digits                 | +5    |
| 🔁 Palindrome                     | +5    |
| 📈 Arithmetic sequence            | +4    |
| 🔥 Special combos (69, 420, 1337) | +4    |
| 🪞 Mirror pattern                 | +3    |
| 📉 Low ID                         | +3    |

> Accounts above threshold are auto-saved.

---

## 🤝 **Contributing**

Contributions are welcome!

```bash
# Fork → Clone → Edit → PR 🚀
```

* Open issues for bugs & ideas
* Submit pull requests
* Improve performance or features

---
<div align="center">

## 🌐 **Connect**

<a href="https://t.me/saeedxdie"><img src="https://img.shields.io/badge/Telegram-Join-blue?style=for-the-badge&logo=telegram"/></a>
<a href="https://x.com/saeedxdie"><img src="https://img.shields.io/badge/Twitter-Follow-black?style=for-the-badge&logo=twitter"/></a>
<a href="https://www.instagram.com/saeedxdie"><img src="https://img.shields.io/badge/Instagram-Follow-E4405F?style=for-the-badge&logo=instagram"/></a>
<a href="https://www.tiktok.com/@saeedxdie"><img src="https://img.shields.io/badge/TikTok-Watch-000000?style=for-the-badge&logo=tiktok"/></a>

</div>

---
<div align="center">

## ⚠️ **Disclaimer**
> This project is for **educational purposes only**.
> Use responsibly and respect platform policies.

---

## 👑 **Credits**
</div>

| Role      | Name        |
| --------- | ----------- |
| Founder   | **SAEED**    |
| Creator   | **TSun Studio**    |
| Collaboration Partners | **Script Kittens** |
---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff0000,100:ff7b00&height=120&section=footer"/>
</p>

---
