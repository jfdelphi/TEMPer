#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import struct
import hid

VENDOR_ID  = 0x0C45
PRODUCT_ID = 0x7401
USAGE_PAGE_SENSOR = 0xFF00  # 65280
USAGE_SENSOR       = 0x01   # laut deinem Dump

SCALE  = 1.0
OFFSET = 0.0


def open_temper():
    """
    Sucht dein TEMPerV1.4 HID-Device und öffnet Interface 1 (Sensor).
    Wird von außen in einer Retry-Schleife aufgerufen.
    """
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    for d in devices:
        if d.get("usage_page") == USAGE_PAGE_SENSOR and d.get("usage") == USAGE_SENSOR:
            print("[INFO] Benutze Device:", d)
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(False)
            return dev
    return None


def decode_temp_from_report(data):
    """
    Temperatur-Decode wie im temper-python fm75-Treiber:
        temp_raw = struct.unpack(">h", data[2:4])[0]
        celsius  = temp_raw / 256.0
    """
    if len(data) < 4:
        raise ValueError(f"Antwort zu kurz: {data}")

    temp_raw = struct.unpack(">h", bytes(data[2:4]))[0]
    celsius = temp_raw / 256.0
    celsius = celsius * SCALE + OFFSET
    return celsius


def read_temperature(dev):
    """
    Sendet den TEMPer-Befehl und liest einen Report.
    Wirft Exceptions bei Fehlern → wird im Main behandelt.
    """
    # Command wie im Original: 01 80 33 01 00 00 00 00
    buf = [0x00, 0x01, 0x80, 0x33, 0x01, 0x00, 0x00, 0x00, 0x00]
    buf += [0x00] * (64 - len(buf))

    written = dev.write(buf)
    if written <= 0:
        raise OSError("Konnte HID-Report nicht schreiben")

    time.sleep(0.1)

    data = dev.read(64, timeout_ms=1000)
    if not data:
        raise OSError("Keine Daten vom Sensor (Timeout)")

    data8 = data[:8]
    temp_c = decode_temp_from_report(data8)
    return temp_c, data8


def main():
    dev = None

    try:
        while True:
            # Falls kein Device offen ist: versuchen zu verbinden
            while dev is None:
                print("[INFO] Versuche TEMPerV1.4 zu finden …")
                dev = open_temper()
                if dev is None:
                    print("[WARN] Kein TEMPer gefunden. Warte 2s und versuche erneut …")
                    time.sleep(2)
                else:
                    print("[INFO] Sensor geöffnet.\n")

            # Mess-Schleife solange das Device funktioniert
            try:
                temp_c, raw = read_temperature(dev)
                if -40.0 <= temp_c <= 125.0:
                    print(f"🌡  {temp_c:6.2f} °C   RAW={raw}")
                else:
                    print(f"[WARN] Unplausibler Wert: {temp_c:.2f} °C   RAW={raw}")
                time.sleep(1.0)

            except (IOError, OSError) as e:
                # Typische Fehler bei Unplug/Replug oder USB-Glitches
                print(f"[ERROR] Lesefehler: {e}. Schließe Device und initialisiere neu …")
                try:
                    dev.close()
                    print("[INFO] Device geschlossen.")
                except Exception:
                    pass
                dev = None
                time.sleep(1)

            except Exception as e:
                # Alles andere auch sauber behandeln, damit die Schleife weiterläuft
                print(f"[ERROR] Unerwarteter Fehler: {e}. Schließe Device und initialisiere neu …")
                try:
                    dev.close()
                    print("[INFO] Device geschlossen.")
                except Exception:
                    pass
                dev = None
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n[INFO] Beendet durch Benutzer.")
    finally:
        if dev is not None:
            try:
                dev.close()
                print("[INFO] Device geschlossen.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
