@echo off
cd /d "E:\TNSVT-V2-Architecture\apps\frontend"
title Vite - TNSVT V2 Frontend
echo Iniciando Vite en puerto 5180...
npm run dev > vite.log 2> vite.err
