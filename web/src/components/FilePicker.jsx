// Native OS file/folder picker via Tauri. Keeps the original props so callers
// (ModManager, SaveAnalyzer) don't change; renders no custom UI of its own.
import { useEffect, useRef } from 'react';
import { open } from '@tauri-apps/plugin-dialog';

function FilePicker({ isOpen, onClose, onSelect, initialPath, selectDirectory = true }) {
  const busy = useRef(false);

  useEffect(() => {
    if (!isOpen || busy.current) return;
    busy.current = true;

    (async () => {
      try {
        const selected = await open({
          directory: selectDirectory,
          multiple: false,
          defaultPath: initialPath || undefined,
        });
        if (selected) {
          onSelect(typeof selected === 'string' ? selected : selected[0]);
        }
      } catch (err) {
        console.error('file dialog error', err);
      } finally {
        busy.current = false;
        onClose();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return null;
}

export default FilePicker;
