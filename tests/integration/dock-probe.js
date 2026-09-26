// Temporary, bounded GNOME Looking Glass observer. No unsafe D-Bus evaluation.
import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export function run(root) {
    if (!root?.startsWith('/')) throw Error('Pass an absolute local evidence directory');
    const write = (name, data) => GLib.file_set_contents(`${root}/${name}`, JSON.stringify(data, null, 2));
    let previous = '';
    const deadline = GLib.get_monotonic_time() + 600 * 1000000;
    write('ready.json', {ready: true, shell: true});
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
        if (GLib.get_monotonic_time() > deadline) {
            write('stopped.json', {reason: 'timeout'});
            return GLib.SOURCE_REMOVE;
        }
        try {
            const [ok, bytes] = GLib.file_get_contents(`${root}/request.json`);
            if (!ok) return GLib.SOURCE_CONTINUE;
            const request = JSON.parse(new TextDecoder().decode(bytes));
            if (request.stage === previous) return GLib.SOURCE_CONTINUE;
            previous = request.stage;
            if (!/^[a-z0-9-]+$/.test(previous)) throw Error('Invalid stage');
            if (request.stop) {
                if (Main.overview.searchEntry.get_text().startsWith('App Faces Dock E2E'))
                    Main.overview.hide();
                write('stopped.json', {reason: 'requested'});
                return GLib.SOURCE_REMOVE;
            }
            if (request.showSearch) {
                Main.overview.show();
                Main.overview.searchEntry.set_text('App Faces Dock E2E');
            }
            if (request.hideSearch) Main.overview.hide();
            const searchActors = [];
            const visit = actor => {
                if ((actor.metaInfo?.id ?? actor.app?.get_id()) === request.launcher && actor.mapped)
                    searchActors.push(actor);
                for (const child of actor.get_children()) visit(child);
            };
            visit(Main.overview.searchController);
            if (request.clickResult) {
                if (searchActors.length !== 1) throw Error('Expected one visible test search result');
                searchActors[0].emit('clicked', 1);
            }
            const tracker = Shell.WindowTracker.get_default();
            const system = Shell.AppSystem.get_default();
            const windows = global.get_window_actors().map(a => a.meta_window)
                .filter(w => request.pids.includes(w.get_pid()));
            const appIds = new Set(windows.map(w => tracker.get_window_app(w)?.get_id()));
            const rect = a => ({position: a.get_transformed_position(), size: a.get_transformed_size(), visible: a.visible, mapped: a.mapped});
            const icons = Main.overview.dash.getAppIcons()
                .filter(a => appIds.has(a.app?.get_id()) || a.app?.get_id() === request.launcher)
                .map(a => ({id: a.app.get_id(), icon: a.app.get_app_info()?.get_icon()?.to_string(),
                    windows: a.app.get_windows().filter(w => request.pids.includes(w.get_pid())).length,
                    actor: rect(a), glyph: rect(a.icon),
                    renderedGicon: a.icon.icon?.gicon?.to_string() ?? null}));
            const result = {
                stage: previous,
                windows: windows.map(w => ({pid: w.get_pid(), wmClass: w.get_wm_class(),
                    instance: w.get_wm_class_instance(), gtkAppId: w.get_gtk_application_id(),
                    clientType: w.get_client_type(), app: tracker.get_window_app(w)?.get_id()})),
                dock: icons,
                search: GioUnix.DesktopAppInfo.search('App Faces Dock E2E'),
                launcherExists: !!system.lookup_app(request.launcher),
                overviewVisible: Main.overview.visible,
                visualSearchResults: searchActors.map(a => ({id: a.metaInfo?.id ?? a.app.get_id(),
                    name: a.metaInfo?.name ?? a.app.get_name(), actor: rect(a), icon: a.icon?.icon?.gicon?.to_string() ?? null})),
                searchResultClicked: !!request.clickResult,
                searchDebug: {
                    text: Main.overview.searchEntry.get_text(),
                    active: Main.overview.searchController.searchActive,
                    terms: Main.overview.searchController._searchResults.terms,
                    resultIds: Object.values(Main.overview.searchController._searchResults._results)
                        .flat().filter(id => id === request.launcher),
                },
            };
            write(`${previous}.json`, result);
            if (request.screenshot) {
                const stream = Gio.File.new_for_path(`${root}/${previous}.png`).replace(null, false, 0, null);
                new Shell.Screenshot().screenshot(false, stream).then(() => stream.close(null))
                    .catch(error => write(`${previous}-screenshot-error.json`, {error: String(error)}));
            }
        } catch (error) {
            write('error.json', {error: String(error)});
        }
        return GLib.SOURCE_CONTINUE;
    });
    return 'App Faces dock observer active for at most 10 minutes';
}
