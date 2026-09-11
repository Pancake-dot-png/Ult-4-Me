// Window-level silence protects autoplay before the page's player is available.
// The page guard also keeps its volume control and dynamically added media at 0.
function silencePageMedia() {
  if (window.__ultPanicSilence) return;
  window.__ultPanicSilence = true;
  const silence = media => {
    if (!(media instanceof HTMLMediaElement)) return;
    if (!media.muted) media.muted = true;
    if (!media.defaultMuted) media.defaultMuted = true;
    if (media.volume !== 0) media.volume = 0;
  };
  const scan = () => document.querySelectorAll('video, audio').forEach(silence);
  for (const name of ['play', 'playing', 'loadedmetadata', 'volumechange']) {
    document.addEventListener(name, event => silence(event.target), true);
  }
  new MutationObserver(records => {
    for (const record of records) for (const node of record.addedNodes) {
      silence(node);
      node.querySelectorAll?.('video, audio').forEach(silence);
    }
  }).observe(document, {childList: true, subtree: true});
  scan();
}

const SILENCE_SCRIPT = `(${silencePageMedia.toString()})()`;

function installPanicAudio(contents, isPanic) {
  const mute = () => {
    if (isPanic() && !contents.isDestroyed()) contents.setAudioMuted(true);
  };
  const mutePlayer = () => {
    mute();
    if (isPanic() && !contents.isDestroyed()) {
      contents.executeJavaScript(SILENCE_SCRIPT).catch(() => {});
    }
  };
  contents.on('did-start-navigation', mute);
  contents.on('did-navigate', mute);
  contents.on('dom-ready', mutePlayer);
  contents.on('media-started-playing', mutePlayer);
}

module.exports = {installPanicAudio, SILENCE_SCRIPT};
