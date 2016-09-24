#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import platform
import signal
import sys
import warnings

from PyQt5.QtCore import QDir, QEvent, QFile, QFileInfo, QSize, Qt, QTime, QUrl
from PyQt5.QtGui import QFontDatabase, QIcon, QMovie, QPalette, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QApplication, QFileDialog,
                             QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
                             QMenu, QMessageBox, QPushButton, QSizePolicy, QSlider,
                             QStyle, QToolBar, QVBoxLayout, QWidget, qApp)

if __name__ == '__main__':
    from videoslider import VideoSlider
    from videoservice import VideoService
else:
    from .videoslider import VideoSlider
    from .videoservice import VideoService

__version__ = '1.0.5'

signal.signal(signal.SIGINT, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
warnings.filterwarnings('ignore')


class VideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        p = self.palette()
        p.setColor(QPalette.Window, Qt.black)
        self.setPalette(p)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key_Enter:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super(VideoWidget, self).keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.setFullScreen(not self.isFullScreen())
        event.accept()


class VidCutter(QWidget):
    def __init__(self, parent):
        super(VidCutter, self).__init__(parent)
        self.parent = parent
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = VideoWidget()
        self.videoService = VideoService(self)

        QFontDatabase.addApplicationFont(os.path.join(self.getAppPath(), 'fonts', 'DroidSansMono.ttf'))

        self.clipTimes = []
        self.inCut = False
        self.movieLoaded = False
        self.timeformat = 'hh:mm:ss'
        self.finalFilename = ''
        self.viewConsole = False

        self.initIcons()
        self.initActions()

        self.toolbar = QToolBar(floatable=False, movable=False, cursor=Qt.PointingHandCursor,
                                iconSize=QSize(28, 28), toolButtonStyle=Qt.ToolButtonTextUnderIcon,
                                styleSheet='QToolBar QToolButton { min-width:82px; margin-left:10px; margin-right:10px; font-size:14px; }')
        self.initToolbar()

        self.aboutMenu = QMenu()
        self.cliplistMenu = QMenu()
        self.initMenus()

        self.seekSlider = VideoSlider(parent=self, sliderMoved=self.setPosition)
        self.seekSlider.installEventFilter(self)

        self.initNoVideo()

        self.cliplist = QListWidget(sizePolicy=QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding),
                                    contextMenuPolicy=Qt.CustomContextMenu, uniformItemSizes=True,
                                    iconSize=QSize(100, 700), dragDropMode=QAbstractItemView.InternalMove,
                                    alternatingRowColors=True, customContextMenuRequested=self.itemMenu,
                                    styleSheet='QListView::item { margin:10px 5px; }')
        self.cliplist.setFixedWidth(185)
        self.cliplist.model().rowsMoved.connect(self.syncClipList)

        listHeader = QLabel(pixmap=QPixmap(os.path.join(self.getAppPath(), 'images', 'clipindex.png')), alignment=Qt.AlignCenter)
        listHeader.setStyleSheet('padding:5px; padding-top:8px; border:1px solid #b9b9b9; border-bottom:none; background-color:qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF, stop: 0.5 #EAEAEA, stop: 0.6 #EAEAEA stop:1 #FFF);')

        self.clipindexLayout = QVBoxLayout(spacing=0)
        self.clipindexLayout.setContentsMargins(0, 0, 0, 0)
        self.clipindexLayout.addWidget(listHeader)
        self.clipindexLayout.addWidget(self.cliplist)

        self.videoLayout = QHBoxLayout()
        self.videoLayout.setContentsMargins(0, 0, 0, 0)
        self.videoLayout.addWidget(self.novideoWidget)
        self.videoLayout.addLayout(self.clipindexLayout)

        self.timeCounter = QLabel('00:00:00 / 00:00:00', autoFillBackground=True, alignment=Qt.AlignCenter,
                                  sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.timeCounter.setStyleSheet('color:#FFFFFF; background:#000000; font-family:Droid Sans Mono; font-size:10.5pt; padding:4px;')

        videoplayerLayout = QVBoxLayout(spacing=0)
        videoplayerLayout.setContentsMargins(0, 0, 0, 0)
        videoplayerLayout.addWidget(self.videoWidget)
        videoplayerLayout.addWidget(self.timeCounter)

        self.videoplayerWidget = QWidget(self, visible=False)
        self.videoplayerWidget.setLayout(videoplayerLayout)

        self.menuButton = QPushButton(icon=self.aboutIcon, flat=True, toolTip='About', statusTip='About',
                                      iconSize=QSize(24, 24), cursor=Qt.PointingHandCursor)
        self.menuButton.setMenu(self.aboutMenu)

        self.muteButton = QPushButton(icon=self.unmuteIcon, flat=True, toolTip='Mute',
                                      statusTip='Toggle audio mute',
                                      cursor=Qt.PointingHandCursor, clicked=self.muteAudio)

        self.volumeSlider = QSlider(Qt.Horizontal, toolTip='Volume', statusTip='Adjust volume level',
                                    cursor=Qt.PointingHandCursor, value=50,
                                    sizePolicy=QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum),
                                    minimum=0, maximum=100, sliderMoved=self.setVolume)

        controlsLayout = QHBoxLayout()
        controlsLayout.addStretch(1)
        controlsLayout.addWidget(self.toolbar)
        controlsLayout.addStretch(1)
        controlsLayout.addWidget(self.muteButton)
        controlsLayout.addWidget(self.volumeSlider)
        controlsLayout.addSpacing(4)
        controlsLayout.addWidget(self.menuButton)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 4)
        layout.addLayout(self.videoLayout)
        layout.addWidget(self.seekSlider)
        layout.addLayout(controlsLayout)

        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.stateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.error.connect(self.handleError)

    def initNoVideo(self):
        novideoImage = QLabel(alignment=Qt.AlignCenter, autoFillBackground=False,
                              pixmap=QPixmap(os.path.join(self.getAppPath(), 'images', 'novideo.png'), 'PNG'),
                              sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding))
        novideoImage.setBackgroundRole(QPalette.Dark)
        novideoImage.setContentsMargins(0, 20, 0, 20)
        self.novideoLabel = QLabel(alignment=Qt.AlignCenter, autoFillBackground=True,
                                   sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.novideoLabel.setBackgroundRole(QPalette.Dark)
        self.novideoLabel.setContentsMargins(0, 20, 15, 60)
        novideoLayout = QVBoxLayout(spacing=0)
        novideoLayout.addWidget(novideoImage)
        novideoLayout.addWidget(self.novideoLabel, alignment=Qt.AlignTop)
        self.novideoMovie = QMovie(os.path.join(self.getAppPath(), 'images', 'novideotext.gif'))
        self.novideoMovie.frameChanged.connect(self.setNoVideoText)
        self.novideoMovie.start()
        self.novideoWidget = QWidget(self, autoFillBackground=True)
        self.novideoWidget.setBackgroundRole(QPalette.Dark)
        self.novideoWidget.setLayout(novideoLayout)

    def initIcons(self):
        self.appIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'vidcutter.png'))
        self.openIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'addmedia.png'))
        self.playIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'play.png'))
        self.pauseIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'pause.png'))
        self.cutStartIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'start.png'))
        self.cutEndIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'end.png'))
        self.saveIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'save.png'))
        self.muteIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'muted.png'))
        self.unmuteIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'unmuted.png'))
        self.upIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'up.png'))
        self.downIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'down.png'))
        self.removeIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'remove.png'))
        self.removeAllIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'remove-all.png'))
        self.successIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'success.png'))
        self.aboutIcon = QIcon(os.path.join(self.getAppPath(), 'images', 'about.png'))

    def initActions(self):
        self.openAction = QAction(self.openIcon, 'Add Media', self, statusTip='Select media source', triggered=self.openFile)
        self.playAction = QAction(self.playIcon, 'Play/Pause', self, statusTip='Play/Pause media', triggered=self.playVideo, enabled=False)
        self.cutStartAction = QAction(self.cutStartIcon, 'Set Start', self, toolTip='Set Start', statusTip='Set start marker', triggered=self.cutStart, enabled=False)
        self.cutEndAction = QAction(self.cutEndIcon, 'Set End', self, statusTip='Set end marker', triggered=self.cutEnd, enabled=False)
        self.saveAction = QAction(self.saveIcon, 'Save', self, statusTip='Save new video', triggered=self.cutVideo, enabled=False)
        self.moveItemUpAction = QAction(self.upIcon, 'Move Up', self, statusTip='Move clip position up in list', triggered=self.moveItemUp, enabled=False)
        self.moveItemDownAction = QAction(self.downIcon, 'Move Down', self, statusTip='Move clip position down in list', triggered=self.moveItemDown, enabled=False)
        self.removeItemAction = QAction(self.removeIcon, 'Remove clip', self, statusTip='Remove selected clip from list', triggered=self.removeItem, enabled=False)
        self.removeAllAction = QAction(self.removeAllIcon, 'Clear list', self, statusTip='Clear all clips from list', triggered=self.clearList, enabled=False)
        self.aboutAction = QAction('About %s' % qApp.applicationName(), self, statusTip='Credits and acknowledgements', triggered=self.aboutInfo)
        self.aboutQtAction = QAction('About Qt', self, statusTip='About Qt', triggered=qApp.aboutQt)
        self.mediaInfoAction = QAction('Media Information', self, statusTip='Media information from loaded video file', triggered=self.mediaInfo, enabled=False)
        # self.viewConsoleAction = QAction('View Console',self, checkable=True, statusTip='View console output from FFmpeg backend commands', triggered=self.toggleConsole)

    def initToolbar(self):
        self.toolbar.addAction(self.openAction)
        self.toolbar.addAction(self.playAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.cutStartAction)
        self.toolbar.addAction(self.cutEndAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.saveAction)

    def initMenus(self):
        self.aboutMenu.addAction(self.mediaInfoAction)
        # self.aboutMenu.addAction(self.viewConsoleAction)
        self.aboutMenu.addSeparator()
        self.aboutMenu.addAction(self.aboutQtAction)
        self.aboutMenu.addAction(self.aboutAction)
        self.cliplistMenu.addAction(self.moveItemUpAction)
        self.cliplistMenu.addAction(self.moveItemDownAction)
        self.cliplistMenu.addSeparator()
        self.cliplistMenu.addAction(self.removeItemAction)
        self.cliplistMenu.addAction(self.removeAllAction)

    def setNoVideoText(self, frame):
        self.novideoLabel.setPixmap(self.novideoMovie.currentPixmap())

    def itemMenu(self, pos):
        globalPos = self.cliplist.mapToGlobal(pos)
        self.moveItemUpAction.setEnabled(False)
        self.moveItemDownAction.setEnabled(False)
        self.removeItemAction.setEnabled(False)
        self.removeAllAction.setEnabled(False)
        index = self.cliplist.currentRow()
        if index != -1:
            if not self.inCut:
                if index > 0:
                    self.moveItemUpAction.setEnabled(True)
                if index < self.cliplist.count() - 1:
                    self.moveItemDownAction.setEnabled(True)
            if self.cliplist.count() > 0:
                self.removeItemAction.setEnabled(True)
        if self.cliplist.count() > 0:
            self.removeAllAction.setEnabled(True)
        self.cliplistMenu.exec_(globalPos)

    def moveItemUp(self):
        index = self.cliplist.currentRow()
        tmpItem = self.clipTimes[index]
        del self.clipTimes[index]
        self.clipTimes.insert(index - 1, tmpItem)
        self.renderTimes()

    def moveItemDown(self):
        index = self.cliplist.currentRow()
        tmpItem = self.clipTimes[index]
        del self.clipTimes[index]
        self.clipTimes.insert(index + 1, tmpItem)
        self.renderTimes()

    def removeItem(self):
        index = self.cliplist.currentRow()
        del self.clipTimes[index]
        if self.inCut and index == self.cliplist.count()-1:
            self.inCut = False
            self.initMediaControls()
        self.renderTimes()

    def clearList(self):
        self.clipTimes.clear()
        self.cliplist.clear()
        self.inCut = False
        self.renderTimes()
        self.initMediaControls()

    def toggleConsole(self):
        self.viewConsole = self.viewConsoleAction.isChecked()

    def mediaInfo(self):
        if self.mediaPlayer.isMetaDataAvailable():
            content = '<table cellpadding="4">'
            for key in self.mediaPlayer.availableMetaData():
                val = self.mediaPlayer.metaData(key)
                if type(val) is QSize:
                    val = '%s x %s' % (val.width(), val.height())
                content += '<tr><td align="right"><b>%s:</b></td><td>%s</td></tr>\n' % (key, val)
            content += '</table>'
            mbox = QMessageBox(windowTitle='Media Information', windowIcon=self.parent.windowIcon(), textFormat=Qt.RichText)
            mbox.setText('<b>%s</b>' % os.path.basename(self.mediaPlayer.currentMedia().canonicalUrl().toLocalFile()))
            mbox.setInformativeText(content)
            mbox.exec_()
        else:
            QMessageBox.critical(self.parent, 'Could not retrieve media information',
                                 '''There was a problem in tring to retrieve media information.
                                    This DOES NOT mean there is a problem with the file and you should
                                    be able to continue using it.''')

    def aboutInfo(self):
        about_html = '''<style>
    a { color:#441d4e; text-decoration:none; font-weight:bold; }
    a:hover { text-decoration:underline; }
    span.title, span.version, span.arch { font-weight:bold; }
    span.title { font-size:26pt !important; }
    span.version { font-size:13pt; }
    span.arch { font-size:10pt; }
</style>
<p>
    <span class="title">%s</span>
</p>
<p>
    <span class="version">Version: %s</span>
    <span class="arch">%s</span>
</p>
<p style="font-size:13px;">
    Copyright &copy; 2016 <a href="mailto:pete@ozmartians.com">Pete Alexandrou</a>
    <br/>
    Website: <a href="%s">%s</a>
</p>
<p style="font-size:13px;">
    Thanks to the folks behind the <b>Qt</b>, <b>PyQt</b> and <b>FFmpeg</b>
    projects for all their hard and much appreciated work.
</p>
<p style="font-size:10px;">
    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.
</p>''' % (qApp.applicationName(), qApp.applicationVersion(),
           'x64' if platform.architecture()[0] == '64bit' else 'x86',
           qApp.organizationDomain(), qApp.organizationDomain())
        QMessageBox.about(self, 'About %s' % qApp.applicationName(), about_html)

    def openFile(self):
        filename, _ = QFileDialog.getOpenFileName(self.parent, caption='Select video', directory=QDir.homePath())
        if filename != '':
            self.loadFile(filename)

    def loadFile(self, filename):
        if not os.path.exists(filename):
            return False
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(filename)))
        self.initMediaControls(True)
        self.cliplist.clear()
        self.clipTimes = []
        self.parent.setWindowTitle('%s %s - %s' % (qApp.applicationName(), qApp.applicationVersion(), os.path.basename(filename)))
        if not self.movieLoaded:
            self.videoLayout.replaceWidget(self.novideoWidget, self.videoplayerWidget)
            self.novideoMovie.stop()
            self.novideoMovie.deleteLater()
            self.novideoWidget.deleteLater()
            self.videoplayerWidget.show()
            self.videoWidget.show()
            self.movieLoaded = True
        self.mediaPlayer.pause()

    def playVideo(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def initMediaControls(self, flag=True):
        self.playAction.setEnabled(flag)
        self.saveAction.setEnabled(False)
        self.cutStartAction.setEnabled(flag)
        self.cutEndAction.setEnabled(False)
        self.mediaInfoAction.setEnabled(flag)
        if flag:
            self.seekSlider.setRestrictValue(0)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)

    def positionChanged(self, progress):
        self.seekSlider.setValue(progress)
        currentTime = self.deltaToQTime(progress)
        totalTime = self.deltaToQTime(self.mediaPlayer.duration())
        self.timeCounter.setText('%s / %s' % (currentTime.toString(self.timeformat), totalTime.toString(self.timeformat)))

    def mediaStateChanged(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.playAction.setIcon(self.pauseIcon)
        else:
            self.playAction.setIcon(self.playIcon)

    def durationChanged(self, duration):
        self.seekSlider.setRange(0, duration)

    def muteAudio(self, muted):
        if self.mediaPlayer.isMuted():
            self.mediaPlayer.setMuted(not self.mediaPlayer.isMuted())
            self.muteButton.setIcon(self.unmuteIcon)
            self.muteButton.setToolTip('Mute')
        else:
            self.mediaPlayer.setMuted(not self.mediaPlayer.isMuted())
            self.muteButton.setIcon(self.muteIcon)
            self.muteButton.setToolTip('Unmute')

    def setVolume(self, volume):
        self.mediaPlayer.setVolume(volume)

    def toggleFullscreen(self):
        self.videoWidget.setFullScreen(not self.videoWidget.isFullScreen())

    def cutStart(self):
        self.clipTimes.append([self.deltaToQTime(self.mediaPlayer.position()), '', self.captureImage()])
        self.cutStartAction.setDisabled(True)
        self.cutEndAction.setEnabled(True)
        self.seekSlider.setRestrictValue(self.seekSlider.value())
        self.inCut = True
        self.renderTimes()

    def cutEnd(self):
        item = self.clipTimes[len(self.clipTimes) - 1]
        selected = self.deltaToQTime(self.mediaPlayer.position())
        if selected.__lt__(item[0]):
            QMessageBox.critical(self.parent, 'Invalid END Time', 'The clip end time must come AFTER it\'s start time. Please try again.')
            return
        item[1] = selected
        self.cutStartAction.setEnabled(True)
        self.cutEndAction.setDisabled(True)
        self.seekSlider.setRestrictValue(0)
        self.inCut = False
        self.renderTimes()

    def syncClipList(self, parent, start, end, destination, row):
        if start < row:
            index = row - 1
        else:
            index = row
        clip = self.clipTimes.pop(start)
        self.clipTimes.insert(index, clip)

    def renderTimes(self):
        self.cliplist.clear()
        self.seekSlider.setCutMode(self.inCut)
        if len(self.clipTimes) > 4:
            self.cliplist.setFixedWidth(200)
        else:
            self.cliplist.setFixedWidth(185)
        for item in self.clipTimes:
            endItem = ''
            if type(item[1]) is QTime:
                endItem = item[1].toString(self.timeformat)
            listitem = QListWidgetItem()
            listitem.setTextAlignment(Qt.AlignVCenter)
            if type(item[2]) is QPixmap:
                listitem.setIcon(QIcon(item[2]))
            self.cliplist.addItem(listitem)
            marker = QLabel('''<style>b { font-size:8pt; } p { margin:5px; }</style>
                            <p><b>START</b><br/>%s</p><p><b>END</b><br/>%s</p>'''
                            % (item[0].toString(self.timeformat), endItem))
            self.cliplist.setItemWidget(listitem, marker)
            listitem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled)
        if len(self.clipTimes) and not self.inCut:
            self.saveAction.setEnabled(True)
        if len(self.clipTimes) == 0 or not type(self.clipTimes[0][1]) is QTime:
            self.saveAction.setEnabled(False)

    @staticmethod
    def deltaToQTime(millisecs):
        secs = millisecs / 1000
        return QTime((secs / 3600) % 60, (secs / 60) % 60, secs % 60, (secs * 1000) % 1000)

    def captureImage(self):
        frametime = self.deltaToQTime(self.mediaPlayer.position()).addSecs(1).toString(self.timeformat)
        inputfile = self.mediaPlayer.currentMedia().canonicalUrl().toLocalFile()
        imagecap = self.videoService.capture(inputfile, frametime)
        if type(imagecap) is QPixmap:
            return imagecap

    def cutVideo(self):
        self.setCursor(Qt.BusyCursor)
        filename = ''
        filelist = []
        source = self.mediaPlayer.currentMedia().canonicalUrl().toLocalFile()
        _, sourceext = os.path.splitext(source)
        if len(self.clipTimes):
            self.finalFilename, _ = QFileDialog.getSaveFileName(self.parent, 'Save video', source,
                                                                'Video files (*%s)' % sourceext)
            if self.finalFilename != '':
                file, ext = os.path.splitext(self.finalFilename)
                index = 1
                for clip in self.clipTimes:
                    runtime = self.deltaToQTime(clip[0].msecsTo(clip[1])).toString(self.timeformat)
                    filename = '%s_%s%s' % (file, '{0:0>2}'.format(index), ext)
                    filelist.append(filename)
                    self.videoService.cut(source, filename, clip[0].toString(self.timeformat), runtime)
                    index += 1
                if len(filelist) > 1:
                    self.joinVideos(filelist, self.finalFilename)
                else:
                    QFile.remove(self.finalFilename)
                    QFile.rename(filename, self.finalFilename)
                self.unsetCursor()
                self.completionDialog()
            return True
        self.unsetCursor()
        return False

    def joinVideos(self, joinlist, filename):
        listfile = os.path.normpath(os.path.join(os.path.dirname(joinlist[0]), '.vidcutter.list'))
        fobj = open(listfile, 'w')
        for file in joinlist:
            fobj.write('file \'%s\'\n' % file.replace("'", "\\'"))
        fobj.close()
        self.videoService.join(listfile, filename)
        try:
            os.remove(listfile)
            for file in joinlist:
                if os.path.isfile(file):
                    os.remove(file)
        except:
            pass

    def completionDialog(self):
        completeMbox = QMessageBox()
        completeMbox.setWindowTitle('Success')
        completeMbox.setWindowIcon(self.parent.windowIcon())
        completeMbox.setIconPixmap(self.successIcon.pixmap(QSize(48, 48)))
        completeMbox.setText('Your video was successfully created at:\n%s\n\nHow would you like to proceed?'
                             % QDir.toNativeSeparators(self.finalFilename))
        play = completeMbox.addButton('Play video', QMessageBox.AcceptRole)
        play.clicked.connect(self.externalPlayer)
        fileman = completeMbox.addButton('Open folder', QMessageBox.AcceptRole)
        fileman.clicked.connect(self.openFolder)
        completeMbox.addButton('Continue', QMessageBox.AcceptRole)
        new = completeMbox.addButton('Start New', QMessageBox.AcceptRole)
        new.clicked.connect(self.startNew)
        completeMbox.setDefaultButton(new)
        completeMbox.setEscapeButton(new)
        completeMbox.exec_()

    def externalPlayer(self):
        if len(self.finalFilename) and os.path.exists(self.finalFilename):
            if sys.platform == 'win32':
                cmd = 'START /B /I "%s"' % self.finalFilename
            elif sys.platform == 'darwin':
                cmd = 'open "%s"' % self.finalFilename
            else:
                cmd = 'xdg-open "%s"' % self.finalFilename
            proc = self.cmdExec(cmd)
            return proc.returncode

    def openFolder(self):
        if len(self.finalFilename) and os.path.exists(self.finalFilename):
            dirname = os.path.dirname(self.finalFilename)
            if sys.platform == 'win32':
                cmd = 'explorer /select,"%s"' % self.finalFilename
            elif sys.platform == 'darwin':
                cmd = 'open "%s"' % dirname
            else:
                cmd = 'xdg-open "%s"' % dirname
            return self.cmdExec(cmd)

    def startNew(self):
        self.clearList()
        self.seekSlider.setValue(0)
        self.seekSlider.setRange(0, 0)
        self.mediaPlayer.setMedia(QMediaContent(None))
        self.initNoVideo()
        self.videoLayout.replaceWidget(self.videoplayerWidget, self.novideoWidget)
        self.initMediaControls(False)

    def wheelEvent(self, event):
        if self.mediaPlayer.isVideoAvailable() or self.mediaPlayer.isAudioAvailable():
            if event.angleDelta().y() > 0:
                newval = self.seekSlider.value() - 1000
            else:
                newval = self.seekSlider.value() + 1000
            self.seekSlider.setValue(newval)
            self.seekSlider.setSliderPosition(newval)
            self.mediaPlayer.setPosition(newval)
        event.accept()

    def keyPressEvent(self, event):
        if self.mediaPlayer.isVideoAvailable() or self.mediaPlayer.isAudioAvailable():
            addtime = 0
            if event.key() == Qt.Key_Left:
                addtime = -1000
            elif event.key() == Qt.Key_PageUp or event.key() == Qt.Key_Up:
                addtime = -10000
            elif event.key() == Qt.Key_Right:
                addtime = 1000
            elif event.key() == Qt.Key_PageDown or event.key() == Qt.Key_Down:
                addtime = 10000
            elif event.key() == Qt.Key_Enter:
                self.toggleFullscreen()
            elif event.key() == Qt.Key_Escape and self.videoWidget.isFullScreen():
                self.videoWidget.setFullScreen(False)
            if addtime != 0:
                newval = self.seekSlider.value() + addtime
                self.seekSlider.setValue(newval)
                self.seekSlider.setSliderPosition(newval)
                self.mediaPlayer.setPosition(newval)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.BackButton and self.cutStartAction.isEnabled():
            self.cutStart()
            event.accept()
        elif event.button() == Qt.ForwardButton and self.cutEndAction.isEnabled():
            self.cutEnd()
            event.accept()
        else:
            super(VidCutter, self).mousePressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonRelease and isinstance(obj, VideoSlider):
            if obj.objectName() == 'VideoSlider' and (self.mediaPlayer.isVideoAvailable() or self.mediaPlayer.isAudioAvailable()):
                obj.setValue(QStyle.sliderValueFromPosition(obj.minimum(), obj.maximum(), event.x(), obj.width()))
                self.mediaPlayer.setPosition(obj.sliderPosition())
        return QWidget.eventFilter(self, obj, event)

    def handleError(self):
        self.unsetCursor()
        self.initMediaControls(False)
        print('ERROR: %s' % self.mediaPlayer.errorString())
        QMessageBox.critical(self.parent, 'Error Alert', self.mediaPlayer.errorString())

    def getAppPath(self):
        return QFileInfo(__file__).absolutePath()
        # if not internal_resource:
        #     if getattr(sys, 'frozen', False):  # for pyinstaller; temp extraction folder
        #       return sys._MEIPASS
        #     return os.path.dirname(os.path.abspath(__file__))
        # return ':/'

    def closeEvent(self, event):
        self.parent.closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.statusBar().showMessage('Ready')
        self.cutter = VidCutter(self)
        self.setCentralWidget(self.cutter)
        self.setAcceptDrops(True)
        self.setWindowTitle('%s %s' % (qApp.applicationName(), qApp.applicationVersion()))
        self.setWindowIcon(self.cutter.appIcon)
        self.setMinimumSize(900, 650)
        self.resize(900, 650)
        if len(sys.argv) >= 2:
            self.cutter.loadFile(sys.argv[1])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()

    def dropEvent(self, event):
        filename = event.mimeData().urls()[0].toLocalFile()
        self.cutter.loadFile(filename)
        event.accept()

    def closeEvent(self, event):
        self.cutter.deleteLater()
        self.deleteLater()
        qApp.quit()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('VidCutter')
    app.setApplicationVersion(__version__)
    app.setOrganizationDomain('http://vidcutter.ozmartians.com')
    app.setQuitOnLastWindowClosed(True)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
