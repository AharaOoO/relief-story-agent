@echo off
title Relief Story Agent - Desktop Dev
echo ======================================================================
echo          RELIEF STORY AGENT - DESKTOP DEVELOPER LAUNCHER
echo ======================================================================
echo.
echo [*] Starting Electron development shell...
echo [*] Frontend dev server and Python API server will launch silently.
echo.
cd /d %~dp0desktop\electron
npm run dev
