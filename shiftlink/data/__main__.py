from shiftlink.data import main


# python -m shiftlink.data의 진입점이다. main의 반환값을 프로세스 종료 코드로 전달한다.
if __name__ == "__main__":
    raise SystemExit(main())
