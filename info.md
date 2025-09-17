## ADSB Aircraft Tracker

Track aircraft in real-time using ADSB data from your dump1090/tar1090 feeder.

### Key Features

🛩️ **Real-time Aircraft Tracking**
- Monitor all aircraft within configurable distance
- Detailed information: tail numbers, flights, altitude, speed, aircraft types
- Top 3 closest aircraft with comprehensive details

🪖 **Smart Military Aircraft Detection**
- Configurable sensitivity: Strict, Moderate, or Loose detection
- Automatic civilian aircraft exclusion (airlines, manufacturers)
- Shows detection reasons for each military aircraft identified
- Supports military callsigns, aircraft types, operators, and patterns

📱 **Intelligent Mobile Notifications**
- Military aircraft alerts with detailed information
- Low altitude aircraft warnings (< 3000ft altitude)
- Emergency squawk code notifications (7700/7600/7500)
- Customizable external ADSB tracker URLs

### Quick Setup

1. Install via HACS or manually
2. Add integration in Settings → Devices & Services
3. Configure your ADSB feeder IP and port (e.g., `192.168.1.100:8085`)
4. Optionally enable military detection and notifications
5. Select mobile device for alerts

### Requirements

- Home Assistant 2023.1+
- ADSB feeder (dump1090/tar1090) on your network
- Mobile app (optional, for notifications)

Perfect for aviation enthusiasts, emergency services, or anyone interested in monitoring air traffic in their area!