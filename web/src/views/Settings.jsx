import { Folder, Bell, Palette, Info } from 'lucide-react';

function Settings() {
    return (
        <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Settings</h1>
                <p className="text-gray-400 mt-1">Configure your preferences</p>
            </div>

            <div className="space-y-6">
                {/* Paths Section */}
                <div className="bg-gray-800 p-6 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <Folder className="text-blue-400" size={24} />
                        <h2 className="text-xl font-bold text-white">File Paths</h2>
                    </div>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Mods Folder</label>
                            <input
                                type="text"
                                defaultValue="~/Documents/Electronic Arts/The Sims 4/Mods"
                                className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Tray Folder</label>
                            <input
                                type="text"
                                defaultValue="~/Documents/Electronic Arts/The Sims 4/Tray"
                                className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600"
                            />
                        </div>
                    </div>
                </div>

                {/* Appearance Section */}
                <div className="bg-gray-800 p-6 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <Palette className="text-purple-400" size={24} />
                        <h2 className="text-xl font-bold text-white">Appearance</h2>
                    </div>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Theme</label>
                            <select className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600">
                                <option>Dark (Default)</option>
                                <option>Light</option>
                                <option>Auto</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* About Section */}
                <div className="bg-gray-800 p-6 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <Info className="text-green-400" size={24} />
                        <h2 className="text-xl font-bold text-white">About</h2>
                    </div>
                    <div className="text-gray-300 space-y-2">
                        <p>
                            <strong>Version:</strong> 2.0.0 (Pro Edition)
                        </p>
                        <p>
                            <strong>Description:</strong> Advanced tool for managing The Sims 4 mods and content
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Settings;
