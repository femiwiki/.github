# 페미위키 개발에 참여하기

페미위키 개발에 관심 가져 주셔서 고맙습니다. 질문은 [디스코드 #개발 채널]에
편하게 남겨 주세요.

## 저장소

| 다루는 것                               | 저장소                        |
| ---------------------------------------- | ----------------------------- |
| 화면 모양, 메뉴, 레이아웃                | [FemiwikiSkin]                |
| 사이트 CSS, 가젯, 시스템 메시지, 루아 모듈 | [remote-gadgets]              |
| 페미위키 전용 기능                       | [UnifiedExtensionForFemiwiki] |
| 설치된 확장기능과 서버 설정              | [docker-mediawiki]            |
| 클라우드 인프라                          | [infra]                       |

어느 저장소인지 모르겠다면 [femiwiki/femiwiki]에 이슈를 남겨 주세요.

## 스킨

```sh
npm i
npm run dev
```

미디어위키와 웹 서버를 내려받아(약 500 MB) <http://localhost:2019>에 위키를
띄웁니다. 로그인은 `Admin` / `Adminpassword`입니다. PR을 올리기 전에
`npm test`를 돌려 주세요.

## 가젯과 위키 문서

remote-gadgets의 `gadgets/`, `pages/`, `lua/` 아래 파일 하나가 위키 문서
하나입니다. 파일 이름은 문서 제목을 URL 인코딩한 것으로,
`gadgets/bookflap/mediawiki%3Agadget-bookflap.js`는
`MediaWiki:Gadget-bookflap.js` 문서입니다. `main`에 머지되면 GitHub
Actions가 바뀐 파일을 위키 문서에 저장합니다. 이 문서들은 위키에서 직접
고치지 말고 PR로 고쳐 주세요.

가젯 JS와 CSS는 머지 전에 내 계정의 [Special:MyPage/common.js]와
[Special:MyPage/common.css]에 붙여 넣어 미리 확인할 수 있습니다.

## PR

커밋 메시지는 [Conventional Commits] 형식을 따릅니다. 언어별 도구와 규칙은
[coding-conventions.md]에 있습니다.

[디스코드 #개발 채널]: https://discord.gg/umzYjJcbvH
[FemiwikiSkin]: https://github.com/femiwiki/FemiwikiSkin
[remote-gadgets]: https://github.com/femiwiki/remote-gadgets
[UnifiedExtensionForFemiwiki]: https://github.com/femiwiki/UnifiedExtensionForFemiwiki
[docker-mediawiki]: https://github.com/femiwiki/docker-mediawiki
[infra]: https://github.com/femiwiki/infra
[femiwiki/femiwiki]: https://github.com/femiwiki/femiwiki/issues
[Special:MyPage/common.js]: https://femiwiki.com/w/Special:MyPage/common.js
[Special:MyPage/common.css]: https://femiwiki.com/w/Special:MyPage/common.css
[Conventional Commits]: https://www.conventionalcommits.org/ko/v1.0.0/
[coding-conventions.md]: https://github.com/femiwiki/femiwiki/blob/main/coding-conventions.md
