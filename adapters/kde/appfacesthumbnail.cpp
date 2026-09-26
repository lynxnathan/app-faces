#include <KIO/ThumbnailCreator>
#include <KPluginFactory>
#include <QImage>
#include <QDebug>
#include <QProcess>
#include <QTemporaryDir>
#include <QUrl>
#include <algorithm>
#include "config.h"

class AppFacesThumbnail final : public KIO::ThumbnailCreator {
    Q_OBJECT
public:
    AppFacesThumbnail(QObject *parent, const QVariantList &args)
        : KIO::ThumbnailCreator(parent, args) {}

    KIO::ThumbnailResult create(const KIO::ThumbnailRequest &request) override {
        if (!request.url().isLocalFile()) return KIO::ThumbnailResult::fail();
        QTemporaryDir directory;
        if (!directory.isValid()) return KIO::ThumbnailResult::fail();
        const QString output = directory.filePath(QStringLiteral("icon.png"));
        const int size = std::clamp(std::max(request.targetSize().width(),
                                           request.targetSize().height()), 1, 1024);
        QProcess process;
        // Candidate path is an argument, never executable code or shell input.
        process.start(QString::fromUtf8(APP_FACES_HELPER),
                      {QStringLiteral("thumbnail"), request.url().toLocalFile(),
                       output, QString::number(size)});
        if (!process.waitForFinished(10000)) {
            process.kill();
            process.waitForFinished(1000);
            return KIO::ThumbnailResult::fail();
        }
        if (process.exitStatus() != QProcess::NormalExit || process.exitCode() != 0) {
            qWarning() << "App Faces helper failed:" << process.readAllStandardError();
            return KIO::ThumbnailResult::fail();
        }
        QImage image(output);
        return image.isNull() ? KIO::ThumbnailResult::fail() : KIO::ThumbnailResult::pass(image);
    }
};
K_PLUGIN_CLASS_WITH_JSON(AppFacesThumbnail, "appfacesthumbnail.json")
#include "appfacesthumbnail.moc"
