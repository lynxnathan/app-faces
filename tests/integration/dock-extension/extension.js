import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class DockProof extends Extension {
    enable() {
        const output = GLib.getenv('APP_FACES_PROOF_OUTPUT');
        const expected = GLib.getenv('APP_FACES_PROOF_ICON');
        const desktopId = GLib.getenv('APP_FACES_PROOF_DESKTOP_ID');
        const wmClass = GLib.getenv('APP_FACES_PROOF_WM_CLASS');
        if (!output || !desktopId || !wmClass || GLib.getenv('APP_FACES_PRIVATE_SHELL') !== '1')
            throw Error('This test extension requires a private shell');
        const write = (name, data) => GLib.file_set_contents(`${output}/${name}`, JSON.stringify(data, null, 2));
        const start = GLib.get_monotonic_time();
        let launched = false;
        let stable = 0;
        let latest = {};
        write('ready.json', {privateShell: true});
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            try {
                if (GLib.get_monotonic_time() - start > 90000000)
                    throw Error(`Timed out waiting for application dock: ${JSON.stringify(latest)}`);
                const app = Shell.AppSystem.get_default().lookup_app(desktopId);
                if (!app || Main.layoutManager._startingUp) return GLib.SOURCE_CONTINUE;
                if (!launched) {
                    Main.overview.hide();
                    app.open_new_window(-1);
                    launched = true;
                    return GLib.SOURCE_CONTINUE;
                }
                const tracker = Shell.WindowTracker.get_default();
                const windows = global.get_window_actors().map(a => a.meta_window)
                    .filter(w => w.get_wm_class() === wmClass);
                const icons = Main.overview.dash.getAppIcons?.()
                    .filter(i => i.app?.get_id() === desktopId) ?? [];
                const icon = icons[0];
                latest = {
                    windows: windows.map(w => ({pid: w.get_pid(), wmClass: w.get_wm_class(),
                        instance: w.get_wm_class_instance(), clientType: w.get_client_type(),
                        desktopId: tracker.get_window_app(w)?.get_id()})),
                    dockEntries: icons.length,
                    dockMapped: icon?.mapped ?? false,
                    gicon: icon?.icon?.icon?.gicon?.to_string() ?? null,
                };
                write('latest.json', latest);
                const correct = windows.length > 0 && windows.every(w => tracker.get_window_app(w)?.get_id() === desktopId)
                    && icons.length === 1 && icon.mapped && latest.gicon === expected;
                stable = correct ? stable + 1 : 0;
                if (stable < 4) return GLib.SOURCE_CONTINUE;
                this._timer = 0;
                const stream = Gio.File.new_for_path(`${output}/dock.png`).replace(null, false, 0, null);
                new Shell.Screenshot().screenshot(false, stream).then(() => {
                    stream.close(null);
                    write('result.json', {passed: true, privateSession: true, personalSessionTouched: false,
                        launcher: desktopId,
                        ...latest, dockPosition: icon.get_transformed_position(), dockSize: icon.get_transformed_size(),
                        screenshot: 'dock.png'});
                }).catch(error => write('result.json', {passed: false, error: String(error)}));
                return GLib.SOURCE_REMOVE;
            } catch (error) {
                write('result.json', {passed: false, error: String(error), ...latest});
                this._timer = 0;
                return GLib.SOURCE_REMOVE;
            }
        });
    }
    disable() {
        if (this._timer) GLib.source_remove(this._timer);
        this._timer = 0;
    }
}
