"""Non-secret user preferences; provider keys never belong here."""
from __future__ import annotations
import json
import os
from pathlib import Path
from .store import managed

PALETTES = {
    'nebula': ('#65d7ff', '#b299ff', '#0a101e'),
    'ember': ('#ffbd73', '#fb86a5', '#160f13'),
    'forest': ('#81e8b2', '#c5dd89', '#091712'),
    'ocean': ('#78dbeb', '#90b8ff', '#091722'),
    'sakura': ('#f5a2c9', '#c6b0ff', '#1b1020'),
    'solar': ('#f4d38a', '#ffa981', '#1d170d'),
    'glacier': ('#9edfff', '#9ce4d7', '#0d1721'),
    'graphite': ('#e1e5ef', '#a7c9ff', '#13161c'),
}

def surface(background: str, foreground: str, amount=.09):
    b = [int(background[i:i+2],16) for i in (1,3,5)]
    f = [int(foreground[i:i+2],16) for i in (1,3,5)]
    return '#' + ''.join(f'{round(x*(1-amount)+y*amount):02x}' for x,y in zip(b,f))

class Preferences:
    def __init__(self):
        base = os.environ.get('FORGE_CONFIG_HOME') or str(Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'agent-forge')
        self.root=Path(base).expanduser()
        if self.root.is_symlink(): raise ValueError('Refusing symlinked preferences directory')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=managed(self.root,'preferences.json')
        self.data={'theme':'nebula','setup_completed':False,'voice_model':'base.en'}
        if self.path.exists():
            value=json.loads(self.path.read_text())
            if value.get('theme') in PALETTES: self.data['theme']=value['theme']
            self.data['setup_completed']=value.get('setup_completed') is True
            if value.get('voice_model') in ('tiny.en','base.en','small.en','tiny','base','small'):
                self.data['voice_model']=value['voice_model']
    def save(self):
        temp=managed(self.root,'preferences.json.tmp');temp.write_text(json.dumps(self.data,indent=2)+'\n');temp.chmod(0o600);temp.replace(self.path)
