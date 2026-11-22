# SortifyPro

## 1. Opis projektu

SortifyPro to desktopowa aplikacja napisana w języku Python, służąca do analizy, organizacji i porządkowania plików. Aplikacja posiada graficzny interfejs użytkownika, umożliwia analizę zawartości folderów, wykrywanie duplikatów, analizę zajętego miejsca oraz sortowanie plików według ich typów.

Projekt został wykonany w ramach przedmiotu **Zaawansowane techniki programowania w języku Python**.

## 2. Technologie

- Python 3.13
- CustomTkinter
- Tkinter
- Threading
- Concurrent Futures
- Regex
- pytest

## 3. Funkcjonalności aplikacji

- Skanowanie folderów i plików.
- Dashboard prezentujący statystyki folderu.
- Sortowanie plików według kategorii.
- Wykrywanie duplikatów.
- Analiza zajętego miejsca na dysku.
- Historia operacji oraz możliwość cofania operacji.
- Ustawienia parametrów wyszukiwania i analizy.
- Benchmark porównujący działanie wątków i procesów.

## 4. Uruchomienie projektu

1. Zainstaluj Python 3.13.
2. Otwórz terminal w katalogu projektu.
3. Utwórz środowisko wirtualne:

   `python -m venv .venv`

4. Aktywuj środowisko:

   Windows:
   `.\.venv\Scripts\activate`

5. Zainstaluj wymagane biblioteki:

   `python -m pip install -r requirements.txt`

6. Uruchom aplikację:

   `python main.py`

## 5. Struktura projektu

- `main.py` – główny plik uruchamiający aplikację.
- `core/` – logika aplikacji, analiza i operacje na plikach.
- `gui/` – graficzny interfejs użytkownika.
- `tests/` – testy projektu.
- `benchmarks/` – pomiary wydajności, jeśli występują w projekcie.
- `README.md` – dokumentacja projektu.
- `requirements.txt` – lista wymaganych bibliotek.

## 6. Mapowanie zaawansowanych technik programowania

| Zagadnienie | Zastosowanie w projekcie |
|---|---|
| Dekoratory funkcji | Pomiar czasu działania, obsługa ponawiania operacji |
| Dekoratory z parametrami | Konfiguracja liczby prób i opóźnienia |
| Dekoratory metod | `property`, `classmethod`, `staticmethod` |
| Iterator | Własne klasy iterujące po plikach lub paczkach danych |
| Generator | Generowanie danych w sposób leniwy z użyciem `yield` |
| Regex | Wyszukiwanie i dopasowywanie wzorców w nazwach plików |
| Wątki | Równoległa obsługa zadań związanych z operacjami wejścia/wyjścia |
| Lock i Queue | Synchronizacja oraz bezpieczna komunikacja pomiędzy wątkami |
| Procesy | Wykorzystanie `ProcessPoolExecutor` do zadań obciążających procesor |
| GIL | Porównanie wykonania sekwencyjnego, wątkowego i procesowego |

## 7. Problemy napotkane podczas realizacji

Podczas realizacji projektu występowały problemy związane z konfiguracją środowiska Python, instalacją bibliotek, obsługą ścieżek do plików oraz integracją poszczególnych modułów z interfejsem graficznym. Problemy rozwiązywano poprzez analizę komunikatów błędów, poprawę konfiguracji i testowanie działania aplikacji.

## 8. Bezpieczeństwo

Aplikacja umożliwia przygotowanie podglądu operacji przed rozpoczęciem sortowania. Pliki nie są przenoszone bez zatwierdzenia operacji przez użytkownika. Historia operacji pozwala na cofnięcie wybranych zmian.