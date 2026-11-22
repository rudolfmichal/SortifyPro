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

## Benchmark GIL – wyniki pomiarów

Pomiary wykonano w środowisku Python 3.13.5, Windows 11, na procesorze z 8 rdzeniami. GIL był włączony. Test obejmował 8 zadań, po 8 MB danych na zadanie, z wykorzystaniem 8 workerów.

| Scenariusz | Sekwencyjnie | Wątki | Procesy |
|---|---:|---:|---:|
| I/O (symulowane oczekiwanie) | 0.40 s | 0.05 s | 0.59 s |
| CPU – czysty Python (Adler-32) | 1.43 s | 1.34 s | 0.77 s |
| CPU – biblioteka C (SHA-256) | 0.08 s | 0.02 s | 0.51 s |

### Wnioski dotyczące GIL

W przypadku zadań I/O zastosowanie wątków znacząco skróciło czas wykonania, ponieważ w trakcie oczekiwania na operacje wątki mogą wykonywać inne zadania. W przeprowadzonym teście czas zmniejszył się z 0,40 s do 0,05 s. W zadaniach CPU wykonywanych w czystym Pythonie wątki nie przyniosły istotnego przyspieszenia, ponieważ GIL ogranicza równoległe wykonywanie kodu Python w wielu wątkach. W tym scenariuszu najlepszy wynik uzyskano przy wykorzystaniu procesów, które mogą wykonywać obliczenia na wielu rdzeniach. Dla SHA-256 wątki uzyskały najlepszy wynik, ponieważ operacje wykonywane w bibliotece C mogą zwalniać GIL. Procesy okazały się nieefektywne w tym przypadku ze względu na dodatkowy narzut związany z ich uruchamianiem i obsługą. Wyniki pokazują, że dobór metody współbieżności powinien zależeć od rodzaju wykonywanego zadania. Wątki najlepiej sprawdzają się w operacjach I/O, natomiast procesy są korzystne dla obliczeń CPU wykonywanych w Pythonie.

### Problemy napotkane podczas realizacji

Podczas realizacji projektu napotkano problemy związane z konfiguracją środowiska Python oraz uruchamianiem aplikacji na różnych komputerach. Konieczne było instalowanie wymaganych bibliotek i zapewnienie poprawnego działania interfejsu graficznego. W trakcie testowania sprawdzano poprawność skanowania plików, wykrywania duplikatów, analizowania zajętości dysku oraz zapisywania historii operacji. Dodatkowym wyzwaniem było porównanie wydajności metod sekwencyjnych, wątkowych i procesowych, a także interpretacja wpływu GIL na różne typy zadań.
