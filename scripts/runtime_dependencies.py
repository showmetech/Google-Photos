"""Copy only pinned distributions, including their native wheel payloads."""
import base64
import hashlib
import importlib.metadata
import re
import shutil
from pathlib import Path


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def copy_pinned_distributions(seed, target, requirements):
    source = (Path(seed) / 'Lib/site-packages').resolve()
    target = Path(target)
    available = {normalized(d.metadata['Name']): d
                 for d in importlib.metadata.distributions(path=[str(source)])}
    for line in Path(requirements).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, version = line.split('==')
        distribution = available.get(normalized(name))
        if distribution is None or distribution.version != version:
            raise RuntimeError(f'Isolated seed must contain {name}=={version}')
        if not distribution.files:
            raise RuntimeError(f'Missing installed-file RECORD: {name}')
        for item in distribution.files:
            path = Path(distribution.locate_file(item)).resolve()
            if not path.is_relative_to(source):
                raise RuntimeError(f'Distribution file outside site-packages: {name}')
            relative = path.relative_to(source)
            if '__pycache__' in relative.parts or path.suffix == '.pyc':
                continue
            if item.hash:
                digest = hashlib.new(item.hash.mode, path.read_bytes()).digest()
                if base64.urlsafe_b64encode(digest).rstrip(b'=').decode() != item.hash.value:
                    raise RuntimeError(f'Installed-file RECORD hash mismatch: {name}')
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
