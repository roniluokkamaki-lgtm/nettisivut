# Nettisivut – suunnittelumuistiinpanot

*(English version below / englanninkielinen versio alempana)*

## 1. Tarkoitus ja periaatteet

**Mikä sivusto on:** Maalausten portfolio ja kevyt verkkokauppa sekä esittely tekijästä.
Kävijä voi selata teoksia, nähdä hinnat ja ostaa maalauksen ottamalla yhteyttä sähköpostilla.

**Ohjaavat periaatteet:**
- **Käsin koodattu, ysäri-henki.** Selkeä perusrakenne: taulukkomaiset asettelut, näkyvät reunat,
  tavalliset linkit. Ei hero-osioita, kortteja tai muita valmiiden pohjien maneereja.
- **Tekninen yksinkertaisuus.** Pelkkä HTML ja CSS, ei frameworkeja, ei build-vaihetta.
- **Staattinen oletuksena.** Sivusto on olemassa antaakseen tietoa, ei esitelläkseen mitä
  HTML ja JavaScript osaavat. Ainoa hyväksytty dynaaminen poikkeus on maalausten katselutila (ks. 3.3).
- **Kaiken pitää toimia.** Ks. tekniset vaatimukset, kohta 6.

## 2. Sivurakenne

| Sivu | Sisältö |
|---|---|
| Etusivu | Lyhyt esittely, profiilikuva, sisäänkäynti galleriaan |
| Galleria | Kaikki maalaukset, luokittelun mukainen selaus, katselutila |
| Tekijä / yhteystiedot | Esittely, sähköpostiosoite, musiikki |
| Ostaminen | Miten tilaus, toimitus ja maksu toimivat |

## 3. Galleria ja kauppa

### 3.1 Teoksen tiedot
Jokaisesta maalauksesta näytetään:
- nimi, vuosi, tekniikka, koko
- hinta (myynnissä olevista)
- saatavuus: myynnissä / myyty / ei myynnissä

### 3.2 Luokittelu ja selaus
Teoksia voi selata kolmella tavalla:
- teeman tai sarjan mukaan
- vuoden mukaan
- tekniikan mukaan

### 3.3 Katselutila (hyväksytty dynaaminen poikkeus)
- Seuraava / edellinen -selaus ilman paluuta gallerianäkymään.
- Zoomaus yksityiskohtiin (siveltimenjälki lähikuvassa).

### 3.4 Ostaminen
- "Osta"-linkki avaa kävijän sähköpostiohjelman siten, että aihe ja maalauksen nimi ovat valmiiksi täytettyinä (mailto).
- Sähköpostiosoite näkyy lisäksi tavallisena tekstinä.

## 4. Visuaalinen ilme

- **Tunnelma:** cyberpunk-underground. Tarkoituksellinen kontrasti perinteisempien maalausten kanssa.
- **Fontti:** valmis tikkukirjainfontti (ei oma). Fontin valinta avoinna.
- **Profiilikuva:** passikuvasta otettu kuva. Kuva lisätään projektikansioon myöhemmin.
- **Väriteema:** _[paikkamerkki – päätetään myöhemmin]_
  Alkuperäinen ajatus: kulunut lämmin-kylmä harmaa tausta, tekstit vaimennettua limenkeltaista ja pinkkiä.

## 5. Musiikki

- Taustalla oma teknokappale.
- Oletuksena pois päältä. Kävijä käynnistää musiikin play-painikkeesta, joka toimii myös mykistyksenä.
- Kappale ei ole vielä valmis (ks. avoimet asiat).

## 6. Tekniset vaatimukset

- Ei rikkinäisiä linkkejä tai kuvia, ei placeholder-sisältöä julkaistussa versiossa.
- Toimii puhelimella: luettava ja käytettävä myös pienellä näytöllä.
- Toimii kaikissa pääselaimissa: Chrome, Firefox, Safari, Edge.
- Nopea ja luotettava: ei riippuvuutta ulkoisista palveluista.

## 7. Hylätyt ideat

- **Tekoälychatbot** (matrix-tyylinen terminaali, "typing"-efekti). Jätetty pois kokonaan.
  Cyberpunk-tunnelma säilyy ilman sitä.
- **Carhartt-lippis-väripaletti.** Korvattu väriteeman paikkamerkillä.

## 8. Avoimet asiat / tehtävät

- [ ] Lisää profiilikuva projektikansioon
- [ ] Valitse tikkukirjainfontti
- [ ] Päätä väriteema
- [ ] Viimeistele teknokappale ja lisää äänitiedosto
- [ ] Kirjoita Ostaminen-sivun sisältö (tilaus, toimitus, maksu)
- [ ] Listaa maalaukset tietoineen (nimi, vuosi, tekniikka, koko, hinta, saatavuus, teema/sarja)

---

# Website – design notes (English)

## 1. Purpose and principles

**What the site is:** A painting portfolio and a light web store, plus an introduction to the artist.
Visitors can browse the works, see prices, and buy a painting by getting in touch by email.

**Guiding principles:**
- **Hand-coded, 90s spirit.** Clear basic structure: table-like layouts, visible borders, plain links.
  No hero sections, cards, or other mannerisms of ready-made templates.
- **Technical simplicity.** Plain HTML and CSS, no frameworks, no build step.
- **Static by default.** The site exists to give information, not to show off what HTML and
  JavaScript can do. The only accepted dynamic exception is the painting viewing mode (see 3.3).
- **Everything must work.** See technical requirements, section 6.

## 2. Site structure

| Page | Content |
|---|---|
| Front page | Short intro, profile picture, entry to the gallery |
| Gallery | All paintings, browsing by category, viewing mode |
| About / contact | Introduction, email address, music |
| Buying | How ordering, shipping and payment work |

## 3. Gallery and store

### 3.1 Painting details
Each painting shows:
- title, year, technique, size
- price (for works for sale)
- availability: for sale / sold / not for sale

### 3.2 Categories and browsing
Works can be browsed in three ways:
- by theme or series
- by year
- by technique

### 3.3 Viewing mode (the accepted dynamic exception)
- Next / previous browsing without returning to the gallery view.
- Zoom into detail (brushwork up close).

### 3.4 Buying
- A "Buy" link opens the visitor's email app with the subject and painting name prefilled (mailto).
- The email address is also shown as plain text.

## 4. Visual identity

- **Mood:** cyberpunk underground. A deliberate contrast with the more traditional paintings.
- **Font:** an existing block-capital (hand-lettered style) font, not self-made. Choice still open.
- **Profile picture:** a photo taken of a passport photo. To be added to the project folder later.
- **Color theme:** _[placeholder – to be decided]_
  Original idea: worn warm-cold grey background, toned-down lime yellow and pink text.

## 5. Music

- Own techno track in the background.
- Off by default. The visitor starts it with a play button, which also acts as mute.
- The track is not finished yet (see open items).

## 6. Technical requirements

- No broken links or images, no placeholder content in the published version.
- Works on phones: readable and usable on small screens.
- Works in all major browsers: Chrome, Firefox, Safari, Edge.
- Fast and robust: no dependency on external services.

## 7. Dropped ideas

- **AI chatbot** (Matrix-style terminal, "typing" effect). Left out entirely.
  The cyberpunk mood stays without it.
- **Carhartt-cap color palette.** Replaced by the color theme placeholder.

## 8. Open items / to-do

- [ ] Add the profile picture to the project folder
- [ ] Choose the block-capital font
- [ ] Decide the color theme
- [ ] Finish the techno track and add the audio file
- [ ] Write the Buying page content (ordering, shipping, payment)
- [ ] List the paintings with details (title, year, technique, size, price, availability, theme/series)
