import assert from 'node:assert/strict';
import test from 'node:test';

import {
    buildProfileConfigPatch,
    chooseProfileDefaultPath,
    deriveProfileFolders,
    normalizeProfileConfig,
    profileDefaultsFromConfig,
} from './settingsModel.js';

test('normalizes profile config with default Sims 4 folder and deduped known profiles', () => {
    const normalized = normalizeProfileConfig({
        active_sims4_profile: '/Users/gabi/Documents/Electronic Arts/The Sims 4',
        sims4_profiles: [
            '/Users/gabi/Documents/Electronic Arts/The Sims 4',
            '',
            '/Users/gabi/Documents/Electronic Arts/The Sims 4 ',
            '/Volumes/External/The Sims 4',
        ],
    });

    assert.deepEqual(normalized, {
        activeProfile: '/Users/gabi/Documents/Electronic Arts/The Sims 4',
        profiles: [
            '/Users/gabi/Documents/Electronic Arts/The Sims 4',
            '/Volumes/External/The Sims 4',
        ],
    });
});

test('falls back to last scan path parent when no active profile is stored', () => {
    const normalized = normalizeProfileConfig({
        last_scan_path: '/Users/gabi/Documents/Electronic Arts/The Sims 4/Mods',
    });

    assert.equal(normalized.activeProfile, '/Users/gabi/Documents/Electronic Arts/The Sims 4');
    assert.deepEqual(normalized.profiles, ['/Users/gabi/Documents/Electronic Arts/The Sims 4']);
});

test('derives Sims folders from the active profile without mutating anything', () => {
    assert.deepEqual(deriveProfileFolders('/Users/gabi/Documents/Electronic Arts/The Sims 4'), [
        { key: 'mods', label: 'Mods', path: '/Users/gabi/Documents/Electronic Arts/The Sims 4/Mods' },
        { key: 'tray', label: 'Tray', path: '/Users/gabi/Documents/Electronic Arts/The Sims 4/Tray' },
        { key: 'saves', label: 'Saves', path: '/Users/gabi/Documents/Electronic Arts/The Sims 4/saves' },
        { key: 'cache', label: 'Cache', path: '/Users/gabi/Documents/Electronic Arts/The Sims 4' },
    ]);
});

test('builds config patch that preserves existing profiles and updates scan path', () => {
    const patch = buildProfileConfigPatch(
        '/Volumes/External/The Sims 4',
        ['/Users/gabi/Documents/Electronic Arts/The Sims 4'],
    );

    assert.deepEqual(patch, {
        active_sims4_profile: '/Volumes/External/The Sims 4',
        sims4_profiles: [
            '/Volumes/External/The Sims 4',
            '/Users/gabi/Documents/Electronic Arts/The Sims 4',
        ],
        last_scan_path: '/Volumes/External/The Sims 4/Mods',
    });
});

test('derives cross-view default paths from active profile config', () => {
    assert.deepEqual(
        profileDefaultsFromConfig({
            active_sims4_profile: '/Profiles/Main/The Sims 4',
        }),
        {
            simsPath: '/Profiles/Main/The Sims 4',
            modsPath: '/Profiles/Main/The Sims 4/Mods',
            trayPath: '/Profiles/Main/The Sims 4/Tray',
            savesPath: '/Profiles/Main/The Sims 4/saves',
            cachePath: '/Profiles/Main/The Sims 4',
        },
    );
});

test('route-specific stored paths override profile defaults', () => {
    const defaults = profileDefaultsFromConfig({
        active_sims4_profile: '/Profiles/Main/The Sims 4',
    });

    assert.equal(
        chooseProfileDefaultPath(defaults, 'simsPath', '/Manual/The Sims 4', '/Fallback/The Sims 4'),
        '/Manual/The Sims 4',
    );
    assert.equal(
        chooseProfileDefaultPath(defaults, 'trayPath', '', '/Fallback/Tray'),
        '/Profiles/Main/The Sims 4/Tray',
    );
    assert.equal(
        chooseProfileDefaultPath({}, 'missingPath', '', '/Fallback/Mods'),
        '/Fallback/Mods',
    );
});
