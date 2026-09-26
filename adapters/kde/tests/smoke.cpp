#include <KIO/ThumbnailCreator>
#include <KPluginFactory>
#include <KPluginMetaData>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QImage>
#include <QTemporaryDir>
#include <QUrl>
#include <memory>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (argc != 2) return 1;
    auto loaded = KPluginFactory::instantiatePlugin<KIO::ThumbnailCreator>(KPluginMetaData(QString::fromLocal8Bit(argv[1])));
    if (!loaded.plugin) return 2;
    std::unique_ptr<KIO::ThumbnailCreator> plugin(loaded.plugin);
    QTemporaryDir temp;
    if (!temp.isValid()) return 3;
    qputenv("XDG_DATA_HOME", temp.path().toUtf8());
    qputenv("XDG_DATA_DIRS", (temp.path() + QStringLiteral(":/usr/share")).toUtf8());
    if (!QDir::setCurrent(temp.path())) return 10;
    const QString binary = temp.filePath(QStringLiteral("Example $(touch shell-executed) App"));
    QFile executable(binary);
    if (!executable.open(QIODevice::WriteOnly)) return 4;
    executable.write("#!/bin/sh\ntouch candidate-executed\n");
    executable.close();
    executable.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
    const QString icon = temp.filePath(QStringLiteral("icon.png"));
    QImage image(16, 8, QImage::Format_ARGB32);
    image.fill(Qt::red);
    if (!image.save(icon)) return 5;
    QDir().mkpath(temp.filePath(QStringLiteral("applications")));
    QFile desktop(temp.filePath(QStringLiteral("applications/org.example.App.desktop")));
    if (!desktop.open(QIODevice::WriteOnly)) return 6;
    desktop.write((QStringLiteral("[Desktop Entry]\nType=Application\nName=Example\nExec=\"") + binary +
                   QStringLiteral("\"\nIcon=") + icon + QStringLiteral("\n")).toUtf8());
    desktop.close();
    auto result = plugin->create(KIO::ThumbnailRequest(QUrl::fromLocalFile(binary), QSize(64,64),
                                 QStringLiteral("application/x-executable"), 1, 0));
    if (!result.isValid() || result.image().size() != QSize(64,32)) return 7;
    for (int y = 0; y < result.image().height(); ++y)
        for (int x = 0; x < result.image().width(); ++x)
            if (result.image().pixelColor(x, y) != QColor(Qt::red)) return 11;
    if (QFile::exists(temp.filePath("shell-executed")) ||
        QFile::exists(temp.filePath("candidate-executed"))) return 12;
    auto remote = plugin->create(KIO::ThumbnailRequest(QUrl(QStringLiteral("https://example.org/app")),
                                 QSize(64,64), QStringLiteral("application/x-executable"), 1, 0));
    if (remote.isValid()) return 8;
    auto missing = plugin->create(KIO::ThumbnailRequest(QUrl::fromLocalFile(temp.filePath("missing")),
                                  QSize(64,64), QStringLiteral("application/x-executable"), 1, 0));
    return missing.isValid() ? 9 : 0;
}
