import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Package } from 'lucide-react';

function ModThumbnail({ path, className }) {
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let active = true;
    invoke('get_thumbnail', { path })
      .then((url) => {
        if (active) setSrc(url || null);
      })
      .catch(() => {
        if (active) setSrc(null);
      });
    return () => {
      active = false;
    };
  }, [path]);

  if (!src) {
    return (
      <div className={className} aria-hidden>
        <Package size={48} className="text-gray-600" />
      </div>
    );
  }
  return <img src={src} className={className} alt="" loading="lazy" />;
}

export default ModThumbnail;
